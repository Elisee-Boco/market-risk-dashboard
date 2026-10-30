"""Décomposition du risque, tests de résistance, dispositif de limites et performance."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import optimize, stats

from . import obligations as ob
from . import portefeuille as pf
from .modeles_var import var_es_empiriques
from .parametres import FENETRE_HS, FENETRE_PARAM, LIMITES, NIVEAU_ES, NIVEAU_VAR, POSITIONS, SEUIL_VIGILANCE, VALEUR_EUR

MANCHES = ["Taux euro", "Taux dollar", "Actions zone euro", "Actions américaines", "Or", "Change dollar"]
CODES = [p.code for p in POSITIONS]


# ---------------------------------------------------------------------------- décomposition
def scenarios_par_manche(base, i, sc, horizon=1.0) -> pd.DataFrame:
    """Contribution de chaque manche de risque au rendement du portefeuille, scénario par scénario."""
    w = dict(zip(CODES, base["poids"]))
    total = pf.reevaluer(base, i, sc, horizon, detail=True)
    sans_change = pf.reevaluer(base, i, {**sc, "fx": np.zeros_like(sc["fx"])}, horizon, detail=True)
    m = pd.DataFrame(index=total.index)
    m["Taux euro"] = sum(w[c] * total[c] for c in ("liq", "ze2", "ze5", "ze10"))
    m["Taux dollar"] = sum(w[c] * sans_change[c] for c in ("us2", "us5", "us10"))
    m["Actions zone euro"] = w["actze"] * total["actze"]
    m["Actions américaines"] = w["actus"] * sans_change["actus"]
    m["Or"] = w["or"] * sans_change["or"]
    m["Change dollar"] = sum(w[c] * (total[c] - sans_change[c]) for c in ("us2", "us5", "us10", "actus", "or"))
    return m


def decomposition(base, i) -> pd.DataFrame:
    """ES par manche (Euler, simulation historique), VaR par manche (Euler, paramétrique) et VaR autonome."""
    sc = pf.scenarios_facteurs(base, max(1, i - FENETRE_HS + 1), i)
    m = scenarios_par_manche(base, i, sc)
    tot = m.sum(axis=1).to_numpy()
    q = np.quantile(tot, 1 - NIVEAU_ES)
    queue = tot <= q
    es = -tot[queue].mean()
    comp_es = -m[queue].mean()
    # paramétrique : covariance des manches sur 250 séances
    h = pf.manches(base).iloc[max(1, i - FENETRE_PARAM + 1): i + 1]
    cov = h.cov().to_numpy()
    sig = np.sqrt(cov.sum())
    z = stats.norm.ppf(NIVEAU_VAR)
    comp_var = z * cov.sum(axis=1) / sig
    autonome = [var_es_empiriques(m[c].to_numpy())[0] for c in m.columns]
    d = pd.DataFrame({"manche": m.columns, "es_composante": comp_es.values, "part_es": comp_es.values / es,
                      "var_composante_param": comp_var, "part_var_param": comp_var / (z * sig),
                      "var_autonome_hs": autonome})
    d.attrs.update({"es_total": es, "var_param_total": z * sig, "diversification_hs": sum(autonome) - var_es_empiriques(tot)[0],
                    "var_hs_total": var_es_empiriques(tot)[0]})
    return d


def var_sans_position(base, i) -> pd.DataFrame:
    """VaR historique du portefeuille si l'on remplaçait chaque position par des liquidités (VaR incrémentale)."""
    sc = pf.scenarios_facteurs(base, max(1, i - FENETRE_HS + 1), i)
    det = pf.reevaluer(base, i, sc, detail=True)
    w = pd.Series(base["poids"], index=CODES)
    v0 = var_es_empiriques(det.to_numpy() @ w.to_numpy())[0]
    lignes = []
    for c in CODES:
        w2 = w.copy()
        w2["liq"] += w2[c] if c != "liq" else 0
        if c != "liq":
            w2[c] = 0
        v = var_es_empiriques(det.to_numpy() @ w2.to_numpy())[0]
        lignes.append({"position": c, "libelle": next(p.libelle for p in POSITIONS if p.code == c), "poids": w[c],
                       "var_sans": v, "var_incrementale": v0 - v})
    return pd.DataFrame(lignes)


def sensibilites(base, i) -> pd.DataFrame:
    """Duration, convexité et PV01 de chaque position ; exposition au change et aux actions."""
    eur_j, usd_j = base["eur"].iloc[i].to_numpy(), base["usd"].iloc[i].to_numpy()
    ne, nu = base["eur"].columns.values.astype(float), base["usd"].columns.values.astype(float)
    lignes = []
    for p, w in zip(POSITIONS, base["poids"]):
        d = {"position": p.code, "libelle": p.libelle, "classe": p.classe, "devise": p.devise, "poids": w,
             "montant_eur": w * base["valeur"].iloc[i]}
        if p.classe == "obligation":
            s = ob.sensibilites(p, eur_j if p.devise == "EUR" else usd_j, ne if p.devise == "EUR" else nu)
            taux = np.interp(p.maturite, ne if p.devise == "EUR" else nu, eur_j if p.devise == "EUR" else usd_j)
            d.update({"taux": taux, "duration": s["duration"], "convexite": s["convexite"],
                      "pv01_pct_position": s["pv01_pct"], "pv01_pct_portefeuille": s["pv01_pct"] * w,
                      "pv01_eur": s["pv01_pct"] / 100 * d["montant_eur"]})
        lignes.append(d)
    return pd.DataFrame(lignes)


# ---------------------------------------------------------------------------- tests de résistance
CRISES = [
    ("lehman", "Faillite de Lehman Brothers", "2008-09-12", "2008-10-10"),
    ("euro2011", "Crise de la dette de la zone euro, dégradation américaine", "2011-07-29", "2011-08-19"),
    ("taper", "« Taper tantrum » de la Fed", "2013-05-21", "2013-06-24"),
    ("covid", "Covid-19", "2020-02-21", "2020-03-23"),
    ("taux2022", "Choc de taux et d'inflation de 2022", "2022-01-03", "2022-10-21"),
    ("svb", "Faillite de Silicon Valley Bank", "2023-03-08", "2023-03-24"),
    ("yen2024", "Dénouement du portage financé en yens", "2024-07-31", "2024-08-05"),
    ("douane2025", "Droits de douane américains", "2025-04-02", "2025-04-08"),
]


def _vecteur(base, ne_choc=0.0, nu_choc=0.0, sx5e=0.0, spx=0.0, or_=0.0, usd=0.0, pente_eur=0.0):
    ne, nu = base["eur"].columns.values.astype(float), base["usd"].columns.values.astype(float)
    eur = np.full(len(ne), ne_choc) + pente_eur * np.clip((ne - 2) / 8, 0, 1)
    return {"eur": eur[None, :], "usd": np.full((1, len(nu)), nu_choc),
            "prix": np.log1p(np.array([[sx5e, spx, or_]])), "fx": np.log1p(np.array([usd]))}


HYPOTHESES = [
    ("eur200", "Taux euro +200 pb (parallèle)", dict(ne_choc=200)),
    ("usd200", "Taux dollar +200 pb (parallèle)", dict(nu_choc=200)),
    ("tous200", "Taux euro et dollar +200 pb", dict(ne_choc=200, nu_choc=200)),
    ("pente", "Pentification euro : +100 pb sur le 10 ans, 2 ans inchangé", dict(pente_eur=100)),
    ("dollar_m10", "Le dollar perd 10 % face à l'euro", dict(usd=-0.10)),
    ("actions_m30", "Actions −30 %", dict(sx5e=-0.30, spx=-0.30)),
    ("or_m20", "Or −20 %", dict(or_=-0.20)),
    ("stagflation", "Stagflation : taux +150 pb, actions −25 %, dollar −10 %, or +10 %",
     dict(ne_choc=150, nu_choc=150, sx5e=-0.25, spx=-0.25, usd=-0.10, or_=0.10)),
    ("refuge", "Fuite vers la qualité : taux −100 pb, actions −30 %, dollar +10 %, or +15 %",
     dict(ne_choc=-100, nu_choc=-100, sx5e=-0.30, spx=-0.30, usd=0.10, or_=0.15)),
]


def scenario_crise(base, debut, fin) -> tuple[dict, int]:
    d = base["dates"]
    a, b = d.searchsorted(pd.Timestamp(debut)), d.searchsorted(pd.Timestamp(fin), side="right") - 1
    sc = pf.scenarios_facteurs(base, a + 1, b)
    cumul = {k: v.sum(axis=0, keepdims=True) if v.ndim == 2 else np.array([v.sum()]) for k, v in sc.items()}
    return cumul, b - a


def tests_resistance(base, i, seuil_inverse=0.05) -> pd.DataFrame:
    lignes = []
    v = base["valeur"].iloc[i]
    for code, nom, a, b in CRISES:
        sc, n = scenario_crise(base, a, b)
        det = scenarios_par_manche(base, i, sc, horizon=n)
        r = det.sum(axis=1).iloc[0]
        rp = base["r_p"].loc[pd.Timestamp(a):pd.Timestamp(b)].iloc[1:]
        chemin = (1 + rp).cumprod()
        lignes.append({"code": code, "scenario": nom, "type": "historique", "debut": a, "fin": b, "seances": n,
                       "rendement": r, "perte_eur": -r * v, **{f"c_{k}": det[k].iloc[0] for k in MANCHES},
                       "rendement_vecu": chemin.iloc[-1] - 1,
                       "multiple_inverse": multiple_inverse(base, i, sc, n, seuil_inverse)})
    for code, nom, kw in HYPOTHESES:
        sc = _vecteur(base, **kw)
        det = scenarios_par_manche(base, i, sc, horizon=0)
        r = det.sum(axis=1).iloc[0]
        lignes.append({"code": code, "scenario": nom, "type": "hypothétique", "rendement": r, "perte_eur": -r * v,
                       **{f"c_{k}": det[k].iloc[0] for k in MANCHES},
                       "multiple_inverse": multiple_inverse(base, i, sc, 0, seuil_inverse)})
    return pd.DataFrame(lignes)


def multiple_inverse(base, i, sc, horizon, seuil) -> float:
    """Test inversé : par combien multiplier le scénario pour perdre « seuil » de la valeur du portefeuille ?"""
    def perte(k):
        s = {kk: vv * k for kk, vv in sc.items()}
        return -pf.reevaluer(base, i, s, horizon)[0] - seuil
    if perte(1) >= 0:
        return float(optimize.brentq(perte, 1e-6, 1)) if perte(1e-6) < 0 else 0.0
    for k_max in (2, 5, 10, 25):
        if perte(k_max) > 0:
            return float(optimize.brentq(perte, 1, k_max))
    return np.inf


# ---------------------------------------------------------------------------- limites
def limites(base, i, var99, es975, sens: pd.DataFrame) -> pd.DataFrame:
    usd = sens[sens.devise == "USD"].poids.sum() * 100
    pv01_eur = sens[(sens.devise == "EUR") & sens.pv01_pct_portefeuille.notna()].pv01_pct_portefeuille.sum()
    pv01_usd = sens[(sens.devise == "USD") & sens.pv01_pct_portefeuille.notna()].pv01_pct_portefeuille.sum()
    date = base["dates"][i]
    debut_mois = base["valeur"].loc[:date][base["valeur"].loc[:date].index < date.replace(day=1)]
    v_ref = debut_mois.iloc[-1] if len(debut_mois) else base["valeur"].iloc[0]
    perte_mois = max(0.0, -(base["valeur"].iloc[i] / v_ref - 1) * 100)
    valeurs = {"var99_1j": var99 * 100, "es975_1j": es975 * 100, "pv01_eur": pv01_eur, "pv01_usd": pv01_usd,
               "change_usd": usd, "perte_mois": perte_mois}
    lib = {"var99_1j": "VaR 99 % à 1 jour (% de la valeur)", "es975_1j": "Expected Shortfall 97,5 % à 1 jour (%)",
           "pv01_eur": "PV01 courbe euro (% pour +1 pb)", "pv01_usd": "PV01 courbe dollar (% pour +1 pb)",
           "change_usd": "Exposition brute au dollar (%)", "perte_mois": "Perte depuis le début du mois (%)"}
    lignes = []
    for k, x in valeurs.items():
        u = x / LIMITES[k]
        lignes.append({"indicateur": k, "libelle": lib[k], "valeur": x, "limite": LIMITES[k], "utilisation": u,
                       "statut": "rouge" if u >= 1 else ("orange" if u >= SEUIL_VIGILANCE else "vert")})
    return pd.DataFrame(lignes)


# ---------------------------------------------------------------------------- performance
def performance(base, debut=None) -> dict:
    r = base["r_p"].iloc[1:] if debut is None else base["r_p"].loc[debut:].iloc[1:]
    liq = base["r_eur"]["liq"].reindex(r.index)
    n = len(r)
    v = (1 + r).cumprod()
    an = 252
    cagr = v.iloc[-1] ** (an / n) - 1
    vol = r.std() * np.sqrt(an)
    exc = r - liq
    dd = v / v.cummax() - 1
    bas = r[r < 0]
    fin_dd = dd.idxmin()
    debut_dd = v.loc[:fin_dd].idxmax()
    rec = v.loc[fin_dd:][v.loc[fin_dd:] >= v.loc[debut_dd]]
    return {"debut": r.index[0], "fin": r.index[-1], "seances": n, "rendement_total": v.iloc[-1] - 1, "cagr": cagr,
            "volatilite": vol, "sharpe": exc.mean() / exc.std() * np.sqrt(an),
            "sortino": exc.mean() * an / (np.sqrt((bas ** 2).sum() / n) * np.sqrt(an)),
            "baisse_max": dd.min(), "debut_baisse": debut_dd, "creux": fin_dd,
            "retour": rec.index[0] if len(rec) else None, "calmar": cagr / -dd.min(),
            "asymetrie": stats.skew(r), "kurtosis": stats.kurtosis(r), "pire_jour": r.min(), "date_pire_jour": r.idxmin(),
            "meilleur_jour": r.max(), "part_jours_positifs": (r > 0).mean(),
            "rendement_liquidites": (1 + liq).prod() ** (an / n) - 1}


def attribution(base) -> pd.DataFrame:
    """Contribution de chaque manche au gain total, en euros (exacte : le portefeuille est rééquilibré chaque jour)."""
    m = pf.manches(base).iloc[1:]
    v_prec = base["valeur"].shift(1).iloc[1:]
    contrib = m.mul(v_prec, axis=0)
    an = contrib.groupby(contrib.index.year).sum()
    an["Total"] = an.sum(axis=1)
    return an


def rendements_annuels(base) -> pd.DataFrame:
    r = base["r_eur"].iloc[1:]
    d = (1 + r).groupby(r.index.year).prod() - 1
    d["portefeuille"] = (1 + base["r_p"].iloc[1:]).groupby(base["r_p"].index[1:].year).prod() - 1
    return d


# ---------------------------------------------------------------------------- couverture du dollar
def couverture(base, i, ratios=(0, 0.25, 0.5, 0.75, 1.0)) -> pd.DataFrame:
    """Faut-il couvrir le dollar ? Effet d'une couverture à terme d'une part h de l'exposition en dollars.

    Couvrir un actif en dollars contre l'euro remplace son rendement de change par le différentiel de taux
    entre l'euro et le dollar (parité des taux d'intérêt couverte) : r_couvert = r_local + (i_EUR − i_USD) Δ.
    On ignore les coûts de transaction et l'écart de base sur le change à terme."""
    w = dict(zip(CODES, base["poids"]))
    expo = sum(w[c] for c in ("us2", "us5", "us10", "actus", "or"))
    fx = pf.manches(base)["Change dollar"]
    d = base["dates"]
    delta = np.r_[0, np.diff(d.values).astype("timedelta64[D]").astype(float)] / 365.0
    i_eur = base["eur"][0.25].shift(1).bfill().to_numpy() / 100
    i_usd = base["usd"][0.25].shift(1).bfill().to_numpy() / 100
    portage = expo * (i_eur - i_usd) * delta
    sc = pf.scenarios_facteurs(base, max(1, i - FENETRE_HS + 1), i)
    lignes = []
    for h in ratios:
        r = (base["r_p"] - h * fx + h * portage).iloc[1:]
        v = (1 + r).cumprod()
        an = 252
        s2 = {**sc, "fx": sc["fx"] * (1 - h)}
        hs = pf.reevaluer(base, i, s2)
        var, _, es = var_es_empiriques(hs)
        lignes.append({"ratio": h, "cagr": v.iloc[-1] ** (an / len(r)) - 1, "volatilite": r.std() * np.sqrt(an),
                       "baisse_max": (v / v.cummax() - 1).min(), "pire_jour": r.min(),
                       "quantile_1pct": -np.quantile(r, 0.01), "var99_hs_jour": var, "es975_hs_jour": es,
                       "cout_portage_annuel": h * portage[1:].sum() / (len(r) / an)})
    return pd.DataFrame(lignes)
