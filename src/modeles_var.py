"""Six modèles de VaR et d'Expected Shortfall.

Conventions : la VaR et l'ES sont des pertes, exprimées en % de la valeur du portefeuille, positives.
La prévision faite à la clôture de la séance t porte sur le rendement de t à t + 1.

  1. Simulation historique (HS) : les variations de facteurs des 500 dernières séances sont appliquées au
     portefeuille du jour, revalorisé complètement (obligations repricées sur la courbe choquée).
  2. Normale : écart-type des 250 dernières séances, moyenne nulle.
  3. Student : même écart-type, queue épaisse ; degrés de liberté estimés par maximum de vraisemblance.
  4. EWMA (RiskMetrics) : variance à décroissance exponentielle, λ = 0,94.
  5. Simulation historique filtrée (FHS) : GARCH(1,1) estimé sur 1 000 séances ; on ré-échelonne les
     résidus standardisés par la volatilité prévue (Barone-Adesi, Giannopoulos et Vosper, 1999).
  6. Monte-Carlo : 20 000 tirages de facteurs selon une loi de Student multivariée de covariance EWMA,
     revalorisation complète ; sert à l'horizon de 10 jours et à la mesure des non-linéarités.

Au début de l'échantillon, faute d'historique, les fenêtres sont prises aussi longues que possible, avec un
minimum de 250 séances (une année, le minimum de Bâle).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import optimize, signal, stats

from . import portefeuille as pf
from .parametres import (FENETRE_GARCH, FENETRE_HS, FENETRE_PARAM, GRAINE, LAMBDA_EWMA, N_MONTE_CARLO, NIVEAU_ES,
                         NIVEAU_VAR, REESTIMATION_GARCH)

MINIMUM = 250
MODELES = ["hs", "normale", "student", "ewma", "fhs"]
LIBELLES = {"hs": "Simulation historique", "normale": "Normale", "student": "Student", "ewma": "EWMA (RiskMetrics)",
            "fhs": "Simulation historique filtrée (GARCH)", "mc": "Monte-Carlo"}
Z_VAR = stats.norm.ppf(NIVEAU_VAR)
Z_ES = stats.norm.ppf(NIVEAU_ES)


# ---------------------------------------------------------------------------- mesures empiriques
def var_es_empiriques(r: np.ndarray, niveau_var=NIVEAU_VAR, niveau_es=NIVEAU_ES) -> tuple[float, float, float]:
    """VaR à niveau_var, VaR et ES à niveau_es, à partir d'un échantillon de rendements (en fraction)."""
    q_var = np.quantile(r, 1 - niveau_var)
    q_es = np.quantile(r, 1 - niveau_es)
    es = r[r <= q_es].mean()
    return -q_var, -q_es, -es


def es_normale(sigma, niveau=NIVEAU_ES):
    z = stats.norm.ppf(niveau)
    return sigma * stats.norm.pdf(z) / (1 - niveau)


def var_student(sigma, nu, niveau):
    s = sigma * np.sqrt((nu - 2) / nu)
    return -stats.t.ppf(1 - niveau, nu) * s


def es_student(sigma, nu, niveau=NIVEAU_ES):
    s = sigma * np.sqrt((nu - 2) / nu)
    q = stats.t.ppf(niveau, nu)
    return s * (nu + q ** 2) / (nu - 1) * stats.t.pdf(q, nu) / (1 - niveau)


def ajuster_nu(r: np.ndarray) -> float:
    """Degrés de liberté d'une Student d'écart-type donné, par maximum de vraisemblance (bornés à [2,5 ; 60])."""
    x = r / r.std()

    def nll(nu):
        s = np.sqrt((nu - 2) / nu)
        return -stats.t.logpdf(x / s, nu).sum() + len(x) * np.log(s)
    return float(optimize.minimize_scalar(nll, bounds=(2.5, 60), method="bounded").x)


# ---------------------------------------------------------------------------- GARCH(1,1)
def variances_garch(params, r, v0=None):
    """Variances conditionnelles d'un GARCH(1,1) sans moyenne, par récurrence directe (filtre linéaire)."""
    omega, alpha, beta = params
    v0 = float(np.var(r)) if v0 is None else v0
    e2 = np.r_[v0, r[:-1] ** 2]                   # e2[t] = r[t-1]^2, avec r[-1]^2 remplacé par v0
    # sigma2[t] = omega + alpha e2[t] + beta sigma2[t-1], sigma2[-1] = v0
    x = omega + alpha * e2
    v, _ = signal.lfilter([1.0], [1.0, -beta], x, zi=[beta * v0])
    return v


def ajuster_garch(r: np.ndarray, depart=None) -> tuple[np.ndarray, float]:
    """Quasi-maximum de vraisemblance gaussien avec ciblage de variance (Engle et Mezrich, 1996) :
    omega = variance de l'échantillon × (1 − alpha − beta), ce qui ne laisse que alpha et beta à estimer.
    Renvoie (omega, alpha, beta) et la variance de départ."""
    v0 = float(np.var(r))

    def nll(theta):
        alpha, beta = theta
        if alpha < 1e-6 or beta < 0 or alpha + beta >= 0.999:
            return 1e10
        v = variances_garch((v0 * (1 - alpha - beta), alpha, beta), r, v0)
        return 0.5 * np.sum(np.log(v) + r ** 2 / v)

    x0 = depart[1:] if depart is not None else np.array([0.08, 0.90])
    res = optimize.minimize(nll, x0, method="Nelder-Mead", options={"xatol": 1e-6, "fatol": 1e-8, "maxiter": 1000})
    a, b = res.x
    return np.array([v0 * (1 - a - b), a, b]), v0


# ---------------------------------------------------------------------------- prévisions quotidiennes
def previsions(base: dict, verbeux=False) -> pd.DataFrame:
    """VaR 99 %, VaR 97,5 % et ES 97,5 % de chaque modèle, pour chaque séance (prévision pour le lendemain)."""
    r = base["r_p"].to_numpy()
    n = len(r)
    lignes = {}
    # EWMA récursive
    v_ewma = np.empty(n)
    v_ewma[:MINIMUM] = np.var(r[1:MINIMUM])
    for t in range(MINIMUM, n):
        v_ewma[t] = LAMBDA_EWMA * v_ewma[t - 1] + (1 - LAMBDA_EWMA) * r[t] ** 2
    nu = np.nan
    garch = None
    depart = None
    for i in range(MINIMUM, n):
        x = r[max(1, i - FENETRE_PARAM + 1): i + 1]
        sig = x.std(ddof=1)
        # 1. simulation historique avec revalorisation complète
        sc = pf.scenarios_facteurs(base, max(1, i - FENETRE_HS + 1), i)
        hs = pf.reevaluer(base, i, sc)
        v_hs, v975_hs, es_hs = var_es_empiriques(hs)
        # 3 et 5 : réestimation périodique de la Student et du GARCH
        if (i - MINIMUM) % REESTIMATION_GARCH == 0:
            fen = r[max(1, i - FENETRE_GARCH + 1): i + 1]
            nu = ajuster_nu(fen)
            p, v0 = ajuster_garch(fen, depart)
            depart = p
            vg = variances_garch(p, fen, v0)
            garch = {"p": p, "v": vg[-1], "residus": fen / np.sqrt(vg)}
        om, al, be = garch["p"]
        garch["v"] = om + al * r[i] ** 2 + be * garch["v"]       # variance prévue pour i + 1
        s_g = np.sqrt(garch["v"])
        z_res = garch["residus"]
        v_f, v975_f, es_f = var_es_empiriques(s_g * z_res)
        s_e = np.sqrt(v_ewma[i])
        lignes[base["dates"][i]] = {
            "hs_var99": v_hs, "hs_var975": v975_hs, "hs_es975": es_hs,
            "normale_var99": Z_VAR * sig, "normale_var975": Z_ES * sig, "normale_es975": es_normale(sig),
            "student_var99": var_student(sig, nu, NIVEAU_VAR), "student_var975": var_student(sig, nu, NIVEAU_ES),
            "student_es975": es_student(sig, nu), "student_nu": nu,
            "ewma_var99": Z_VAR * s_e, "ewma_var975": Z_ES * s_e, "ewma_es975": es_normale(s_e),
            "fhs_var99": v_f, "fhs_var975": v975_f, "fhs_es975": es_f,
            "garch_omega": om, "garch_alpha": al, "garch_beta": be, "vol_garch": s_g, "vol_250": sig, "vol_ewma": s_e,
            "rendement_suivant": r[i + 1] if i + 1 < n else np.nan,
        }
        if verbeux and i % 1000 == 0:
            print(i, base["dates"][i].date())
    return pd.DataFrame.from_dict(lignes, orient="index")


# ---------------------------------------------------------------------------- Monte-Carlo et horizon 10 jours
def _facteurs(base, debut, fin):
    sc = pf.scenarios_facteurs(base, debut, fin)
    return np.column_stack([sc["eur"], sc["usd"], sc["prix"], sc["fx"]])


def _decouper(base, X):
    ne, nu = base["f_eur"].shape[1], base["f_usd"].shape[1]
    return {"eur": X[:, :ne], "usd": X[:, ne:ne + nu], "prix": X[:, ne + nu:ne + nu + 3], "fx": X[:, -1]}


def covariance_ewma(base, i, lam=LAMBDA_EWMA, fenetre=FENETRE_HS):
    X = _facteurs(base, max(1, i - fenetre + 1), i)
    w = lam ** np.arange(len(X))[::-1]
    w /= w.sum()
    return (X * w[:, None]).T @ X


def monte_carlo(base, i, horizon=1, n=N_MONTE_CARLO, nu=5, graine=GRAINE, detail=False):
    """Tirages de facteurs selon une Student multivariée de covariance EWMA × horizon, revalorisation complète."""
    rng = np.random.default_rng(graine)
    cov = covariance_ewma(base, i) * horizon
    val, vec = np.linalg.eigh(cov)
    racine = vec * np.sqrt(np.clip(val, 0, None))
    z = rng.standard_normal((n, len(cov))) @ racine.T
    w = rng.chisquare(nu, size=n)
    X = z * np.sqrt((nu - 2) / w)[:, None]
    return pf.reevaluer(base, i, _decouper(base, X), horizon_jours=horizon, detail=detail)


def hs_horizon(base, i, horizon=10, fenetre=FENETRE_HS):
    """Simulation historique sur variations de facteurs cumulées sur « horizon » séances (fenêtres glissantes)."""
    X = _facteurs(base, max(1, i - fenetre + 1), i)
    c = np.cumsum(np.vstack([np.zeros(X.shape[1]), X]), axis=0)
    X10 = c[horizon:] - c[:-horizon]
    return pf.reevaluer(base, i, _decouper(base, X10), horizon_jours=horizon)


def tableau_du_jour(base, prev: pd.DataFrame, i: int) -> pd.DataFrame:
    """VaR et ES des six modèles à la séance i, à 1 et 10 jours."""
    p = prev.loc[base["dates"][i]]
    lignes = []
    for m in MODELES:
        v1, e1 = p[f"{m}_var99"], p[f"{m}_es975"]
        lignes.append({"modele": m, "libelle": LIBELLES[m], "var99_1j": v1, "es975_1j": e1,
                       "var99_10j_racine": v1 * np.sqrt(10), "es975_10j_racine": e1 * np.sqrt(10)})
    mc1 = monte_carlo(base, i, 1)
    mc10 = monte_carlo(base, i, 10)
    v1, _, e1 = var_es_empiriques(mc1)
    v10, _, e10 = var_es_empiriques(mc10)
    lignes.append({"modele": "mc", "libelle": LIBELLES["mc"], "var99_1j": v1, "es975_1j": e1,
                   "var99_10j_racine": v1 * np.sqrt(10), "es975_10j_racine": e1 * np.sqrt(10),
                   "var99_10j_direct": v10, "es975_10j_direct": e10})
    h10 = hs_horizon(base, i, 10)
    v10h, _, e10h = var_es_empiriques(h10)
    lignes[0].update({"var99_10j_direct": v10h, "es975_10j_direct": e10h})
    return pd.DataFrame(lignes)
