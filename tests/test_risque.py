"""Tests du tableau de bord du risque de marché. Lancer : python tests/test_risque.py (ou python -m pytest -q)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import analyses as an
from src import backtest as bt
from src import donnees as dn
from src import modeles_var as mv
from src import obligations as ob
from src import portefeuille as pf
from src.parametres import POSITIONS, VALEUR_EUR

NOEUDS = np.array([0.25, 0.5, 1, 2, 3, 5, 7, 10, 15, 20, 30], dtype=float)
P = {p.code: p for p in POSITIONS}
_BASE = {}


def base():
    if not _BASE:
        _BASE["b"] = pf.construire(dn.charger())
    return _BASE["b"]


# --- Obligations ---------------------------------------------------------------------------

def test_obligation_euro_au_pair_a_l_emission():
    z = np.linspace(2.0, 3.5, len(NOEUDS))
    c = ob.coupon_pair_eur(z, NOEUDS, 10)
    assert abs(ob.prix_eur(z, NOEUDS, np.array(c), 10) - 100) < 1e-9


def test_obligation_americaine_au_pair():
    assert abs(ob.prix_actuariel(4.5, 4.5, 10, 2) - 100) < 1e-9
    assert abs(ob.prix_actuariel(0.0, 0.0, 5, 2) - 100) < 1e-9          # taux nul : limite de la formule


def test_portage_courbe_inchangee():
    """Courbe plate inchangée : un jour de détention rapporte le taux × la durée, ni plus ni moins."""
    z = np.full(len(NOEUDS), 3.0)
    r = ob.pnl_obligation(P["ze5"], z, NOEUDS, np.zeros((1, len(NOEUDS))), horizon_jours=5)[0]
    dt = 5 * 7 / 5 / 365
    assert abs(r - np.expm1(0.03 * dt)) < 2e-6
    y = np.full(len(NOEUDS), 4.0)
    r = ob.pnl_obligation(P["us5"], y, NOEUDS, np.zeros((1, len(NOEUDS))), horizon_jours=5)[0]
    assert abs(r - ((1 + 0.04 / 2) ** (2 * dt) - 1)) < 1e-9


def test_duration_formule_fermee():
    """Duration modifiée d'une obligation au pair semestrielle : (1 − (1 + y/2)^(−2T)) / y."""
    y = np.full(len(NOEUDS), 5.0)
    s = ob.sensibilites(P["us10"], y, NOEUDS)
    attendu = (1 - 1.025 ** -20) / 0.05
    assert abs(s["duration"] - attendu) < 1e-3
    assert s["convexite"] > 0 and abs(s["pv01_pct"] - attendu * 1e-2) < 1e-3


def test_convexite_asymetrie_hausse_baisse():
    """Convexité : le gain d'une baisse de 100 pb dépasse la perte d'une hausse de 100 pb."""
    z = np.full(len(NOEUDS), 3.0)
    chocs = np.vstack([np.full(len(NOEUDS), 100.0), np.full(len(NOEUDS), -100.0)])
    hausse, baisse = ob.pnl_obligation(P["ze10"], z, NOEUDS, chocs, 0)
    assert hausse < 0 < baisse and baisse > -hausse


def test_maturite_constante_courbe_plate():
    d = pd.bdate_range("2024-01-01", periods=30)
    e = pd.DataFrame(3.0, index=d, columns=NOEUDS)
    u = pd.DataFrame(4.0, index=d, columns=[0.25, 0.5, 1, 2, 3, 5, 7, 10, 20])
    r = ob.rendements_maturite_constante(e, u, POSITIONS, d)
    dt = np.r_[0, np.diff(d.values).astype("timedelta64[D]").astype(float)] / 365
    assert np.allclose(r["ze10"][1:], np.expm1(0.03 * dt[1:]), atol=1e-7)
    assert np.allclose(r["us2"][1:], (1.02) ** (2 * dt[1:]) - 1, atol=1e-9)


# --- Portefeuille ---------------------------------------------------------------------------

def test_donnees_et_calendrier():
    b = base()
    assert b["dates"].is_monotonic_increasing and b["dates"].is_unique
    assert not b["r_eur"].isna().any().any() and len(b["dates"]) > 4900
    assert abs(b["valeur"].iloc[-1] - VALEUR_EUR) < 1e-6


def test_rendement_du_portefeuille_est_la_somme_ponderee():
    b = base()
    assert np.allclose(b["r_p"].iloc[1:], b["r_eur"].iloc[1:].to_numpy() @ b["poids"])


def test_manches_additives():
    b = base()
    assert np.allclose(pf.manches(b).sum(axis=1).iloc[1:], b["r_p"].iloc[1:], atol=1e-12)


def test_attribution_reconstitue_le_gain():
    b = base()
    a = an.attribution(b)
    assert abs(a["Total"].sum() - (b["valeur"].iloc[-1] - b["valeur"].iloc[0])) < 1e-3


def test_revalorisation_choc_nul():
    b = base()
    i = len(b["dates"]) - 1
    sc = {"eur": np.zeros((1, b["f_eur"].shape[1])), "usd": np.zeros((1, b["f_usd"].shape[1])),
          "prix": np.zeros((1, 3)), "fx": np.zeros(1)}
    r = pf.reevaluer(b, i, sc, horizon_jours=0)[0]
    assert abs(r) < 1e-12


def test_choc_de_taux_coherent_avec_pv01():
    """Taux euro +1 pb : la perte égale la PV01 euro du portefeuille, à 1 % près."""
    b = base()
    i = len(b["dates"]) - 1
    s = an.sensibilites(b, i)
    pv01 = s[s.devise == "EUR"].pv01_pct_portefeuille.sum() / 100
    sc = {"eur": np.ones((1, b["f_eur"].shape[1])), "usd": np.zeros((1, b["f_usd"].shape[1])),
          "prix": np.zeros((1, 3)), "fx": np.zeros(1)}
    assert abs(-pf.reevaluer(b, i, sc, 0)[0] - pv01) / pv01 < 0.01


# --- Modèles de VaR ------------------------------------------------------------------------

def test_var_es_empiriques_loi_normale():
    x = np.random.default_rng(1).standard_normal(400_000)
    v, v975, es = mv.var_es_empiriques(x)
    assert abs(v - 2.3263) < 0.02 and abs(v975 - 1.96) < 0.015 and abs(es - 2.3378) < 0.02
    assert abs(mv.es_normale(1.0) - 2.3378) < 1e-3


def test_student_plus_prudente_et_formule_es():
    nu = 4.0
    assert mv.var_student(1.0, nu, 0.99) > 2.3263 * 0.99
    x = stats.t.rvs(nu, size=600_000, random_state=2) * np.sqrt((nu - 2) / nu)
    q = np.quantile(x, 0.025)
    assert abs(-x[x <= q].mean() - mv.es_student(1.0, nu)) < 0.03


def test_estimation_des_degres_de_liberte():
    x = stats.t.rvs(5, size=20_000, random_state=3) * 0.01
    assert 4.2 < mv.ajuster_nu(x) < 6.0


def test_garch_retrouve_ses_parametres():
    rng = np.random.default_rng(4)
    omega, alpha, beta, n = 2e-7, 0.08, 0.90, 20_000
    r, v = np.empty(n), omega / (1 - alpha - beta)
    for t in range(n):
        r[t] = np.sqrt(v) * rng.standard_normal()
        v = omega + alpha * r[t] ** 2 + beta * v
    p, _ = mv.ajuster_garch(r)
    assert abs(p[1] - alpha) < 0.02 and abs(p[2] - beta) < 0.03


# --- Backtesting ---------------------------------------------------------------------------

def test_kupiec():
    assert bt.kupiec(10, 1000)["p_pof"] > 0.99
    assert bt.kupiec(30, 1000)["p_pof"] < 1e-5


def test_christoffersen_detecte_les_grappes():
    rng = np.random.default_rng(5)
    iid = (rng.random(5000) < 0.01).astype(int)
    grappes = np.zeros(5000, dtype=int)
    for d in rng.choice(4990, 25, replace=False):
        grappes[d:d + 2] = 1
    assert bt.christoffersen(iid)["p_ind"] > 0.01
    assert bt.christoffersen(grappes)["p_ind"] < 1e-6


def test_zones_de_bale():
    assert [bt.zone_bale(k) for k in (0, 4, 5, 9, 10)] == ["vert", "vert", "orange", "orange", "rouge"]


def test_acerbi_szekely():
    rng = np.random.default_rng(6)
    x = rng.standard_normal(200_000)
    v = np.full(len(x), 1.96)
    juste = bt.acerbi_szekely_z2(x, v, np.full(len(x), mv.es_normale(1.0)))
    sous = bt.acerbi_szekely_z2(x * 1.5, v, np.full(len(x), mv.es_normale(1.0)))
    assert abs(juste) < 0.05 and sous < -0.7


# --- Analyses ------------------------------------------------------------------------------

def test_test_inverse():
    b = base()
    i = len(b["dates"]) - 1
    sc = an._vecteur(b, sx5e=-0.10, spx=-0.10)
    k = an.multiple_inverse(b, i, sc, 0, 0.05)
    s = {kk: vv * k for kk, vv in sc.items()}
    assert abs(-pf.reevaluer(b, i, s, 0)[0] - 0.05) < 1e-6


def test_couverture_nulle_egale_portefeuille():
    b = base()
    c = an.couverture(b, len(b["dates"]) - 1, ratios=(0.0,))
    p = an.performance(b)
    assert abs(c.cagr.iloc[0] - p["cagr"]) < 1e-12 and abs(c.volatilite.iloc[0] - p["volatilite"]) < 1e-12


def test_decomposition_euler_somme_a_l_es():
    b = base()
    d = an.decomposition(b, len(b["dates"]) - 1)
    assert abs(d.part_es.sum() - 1) < 1e-9 and abs(d.part_var_param.sum() - 1) < 1e-9


if __name__ == "__main__":
    tests = [(k, f) for k, f in sorted(globals().items()) if k.startswith("test_")]
    echecs = 0
    for nom, f in tests:
        try:
            f()
            print(f"OK    {nom}")
        except AssertionError as e:
            echecs += 1
            print(f"ÉCHEC {nom} {e}")
    print(f"\n{len(tests) - echecs}/{len(tests)} tests réussis")
    sys.exit(1 if echecs else 0)
