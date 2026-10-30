"""Rendements des positions en euros, facteurs de risque et revalorisation du portefeuille sous scénarios.

Le portefeuille est valorisé en euros : le franc CFA étant arrimé à l'euro (1 € = 655,957 FCFA), un
résultat en euros se convertit en FCFA par un simple produit, sans risque de change supplémentaire.
Les positions en dollars portent, elles, le risque euro/dollar.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import obligations as ob
from .parametres import POSITIONS, VALEUR_EUR


def construire(m: dict) -> dict:
    """À partir des données chargées : rendements en euros de chaque position, facteurs de risque, portefeuille."""
    dates = m["eur"].index
    eur, usd, px = m["eur"], m["usd"], m["prix"]
    delta = np.r_[0, np.diff(dates.values).astype("timedelta64[D]").astype(float)] / 365.0
    # Rendement du dollar exprimé en euros : 1 $ vaut 1/EURUSD euros
    r_fx = (m["eurusd"].shift(1) / m["eurusd"] - 1).fillna(0).to_numpy()
    r_loc = ob.rendements_maturite_constante(eur, usd, POSITIONS, dates)
    z3m = eur[0.25].shift(1).bfill().to_numpy() / 100
    r_loc["liq"] = np.expm1(z3m * delta)
    for p in POSITIONS:
        if p.facteur:
            r_loc[p.code] = (px[p.facteur] / px[p.facteur].shift(1) - 1).fillna(0).to_numpy()
    r_loc = pd.DataFrame(r_loc, index=dates)[[p.code for p in POSITIONS]]
    r_eur = r_loc.copy()
    for p in POSITIONS:
        if p.devise == "USD":
            r_eur[p.code] = (1 + r_loc[p.code]) * (1 + r_fx) - 1
    w = np.array([p.poids for p in POSITIONS])
    r_p = r_eur.to_numpy() @ w
    r_p[0] = 0.0
    indice = np.cumprod(1 + r_p)
    valeur = VALEUR_EUR * indice / indice[-1]          # 100 milliards de FCFA à la date d'arrêté

    # Facteurs de risque : variations de taux aux nœuds (pb), rendements logarithmiques des prix et du change
    f_eur = eur.diff().mul(100).fillna(0)
    f_usd = usd.diff().mul(100).fillna(0)
    f_prix = np.log(px[["sx5e", "spx", "or"]]).diff().fillna(0)
    f_fx = pd.Series(np.log1p(r_fx), index=dates, name="usd_en_eur")
    return {"dates": dates, "r_loc": r_loc, "r_eur": r_eur, "r_fx": pd.Series(r_fx, index=dates), "poids": w,
            "r_p": pd.Series(r_p, index=dates, name="portefeuille"), "valeur": pd.Series(valeur, index=dates, name="valeur_eur"),
            "f_eur": f_eur, "f_usd": f_usd, "f_prix": f_prix, "f_fx": f_fx, "eur": eur, "usd": usd, "z3m": z3m}


def scenarios_facteurs(base: dict, debut: int, fin: int) -> dict:
    """Variations de facteurs observées entre les séances debut et fin (incluses), une par jour."""
    s = slice(debut, fin + 1)
    return {"eur": base["f_eur"].iloc[s].to_numpy(), "usd": base["f_usd"].iloc[s].to_numpy(),
            "prix": base["f_prix"].iloc[s].to_numpy(), "fx": base["f_fx"].iloc[s].to_numpy()}


def reevaluer(base: dict, i: int, sc: dict, horizon_jours: float = 1.0, detail: bool = False):
    """Rendement du portefeuille de la séance i sous chaque scénario de facteurs (revalorisation complète).

    sc : {"eur": (S × nœuds) pb, "usd": (S × nœuds) pb, "prix": (S × 3) log, "fx": (S,) log}.
    Renvoie un vecteur de rendements (ou, si detail, un DataFrame par position)."""
    eur_j = base["eur"].iloc[i].to_numpy()
    usd_j = base["usd"].iloc[i].to_numpy()
    ne, nu = base["eur"].columns.values.astype(float), base["usd"].columns.values.astype(float)
    S = len(sc["fx"])
    fx = np.expm1(sc["fx"])
    prix = np.expm1(sc["prix"])
    cols = {"sx5e": 0, "spx": 1, "or": 2}
    dt = horizon_jours * 7 / 5 / 365.0
    out = {}
    for p in POSITIONS:
        if p.classe == "monetaire":
            r = np.full(S, np.expm1(eur_j[0] / 100 * dt))
        elif p.classe == "obligation":
            if p.devise == "EUR":
                r = ob.pnl_obligation(p, eur_j, ne, sc["eur"], horizon_jours)
            else:
                r = ob.pnl_obligation(p, usd_j, nu, sc["usd"], horizon_jours)
        else:
            r = prix[:, cols[p.facteur]]
        if p.devise == "USD":
            r = (1 + r) * (1 + fx) - 1
        out[p.code] = r
    d = pd.DataFrame(out)
    if detail:
        return d
    return d.to_numpy() @ base["poids"]


def manches(base: dict) -> pd.DataFrame:
    """Rendements des « manches » de risque, additives : taux euro, taux dollar, actions, or, change dollar.

    Pour une position en dollars, (1 + r_local)(1 + r_change) − 1 = r_local + r_change (1 + r_local) : la
    part de change, termes croisés compris, est attribuée au change."""
    w = dict(zip([p.code for p in POSITIONS], base["poids"]))
    rl, rf = base["r_loc"], base["r_fx"]
    m = pd.DataFrame(index=rl.index)
    m["Taux euro"] = sum(w[c] * rl[c] for c in ("liq", "ze2", "ze5", "ze10"))
    m["Taux dollar"] = sum(w[c] * rl[c] for c in ("us2", "us5", "us10"))
    m["Actions zone euro"] = w["actze"] * rl["actze"]
    m["Actions américaines"] = w["actus"] * rl["actus"]
    m["Or"] = w["or"] * rl["or"]
    m["Change dollar"] = sum(w[c] * rf * (1 + rl[c]) for c in ("us2", "us5", "us10", "actus", "or"))
    return m
