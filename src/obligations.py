"""Valorisation des obligations à partir des courbes de taux.

Zone euro : la BCE publie des taux zéro-coupon à composition continue (modèle de Svensson). Une obligation
à coupon annuel se valorise en actualisant chaque flux au taux zéro-coupon de sa date :
    P = somme_k  c · exp(−z(t_k) · t_k)  +  100 · exp(−z(T) · T).

États-Unis : le Trésor publie des taux de rendement au pair (« constant maturity ») à coupon semestriel. Le
taux au pair à la maturité T est, par construction, le rendement actuariel d'une obligation émise au pair
à cette date ; on valorise donc avec la formule actuarielle :
    P = c/y · (1 − (1 + y/2)^(−2T)) + 100 · (1 + y/2)^(−2T).

Portefeuille à maturité constante (Swinkels, 2019) : chaque jour on détient une obligation émise au pair
la veille, de maturité T exactement ; le lendemain elle a T − Δ à courir et on la revalorise sur la
nouvelle courbe. Le rendement obtenu contient le portage (le coupon couru), le glissement sur la courbe
et l'effet du mouvement des taux.
"""
from __future__ import annotations

import numpy as np

from .donnees import interpoler, interpoler_par_ligne

BP = 1e-4


# ---------------------------------------------------------------------------- zone euro (zéro-coupon)
def _dates_flux(T: float, f: int, ecoule: float = 0.0) -> np.ndarray:
    """Dates des flux restants (en années) d'une obligation de maturité initiale T, après « ecoule » années."""
    t = np.arange(1, int(round(T * f)) + 1) / f - ecoule
    return t[t > 1e-9]


def coupon_pair_eur(z_noeuds: np.ndarray, noeuds, T: float, f: int = 1) -> np.ndarray:
    """Coupon annuel (en % du nominal) qui fait coter l'obligation au pair sur la courbe zéro-coupon."""
    t = _dates_flux(T, f)
    z = interpoler(z_noeuds, noeuds, t) / 100            # (dates, flux)
    d = np.exp(-z * t)
    return 100 * f * (1 - d[..., -1]) / d.sum(axis=-1)


def prix_eur(z_noeuds: np.ndarray, noeuds, coupon, T: float, ecoule: float = 0.0, f: int = 1) -> np.ndarray:
    """Prix « pied de coupon compris » (dirty) de l'obligation, nominal 100."""
    t = _dates_flux(T, f, ecoule)
    z = interpoler(z_noeuds, noeuds, t) / 100
    d = np.exp(-z * t)
    c = np.asarray(coupon, dtype=float)[..., None] / f
    return (c * d).sum(axis=-1) + 100 * d[..., -1]


# ---------------------------------------------------------------------------- États-Unis (au pair)
def prix_actuariel(y, coupon, T: float, f: int = 2, ecoule: float = 0.0) -> np.ndarray:
    """Prix dirty d'une obligation émise au pair il y a « ecoule » années, au rendement y (en %).

    Le prix au jour du dernier coupon est la formule actuarielle ; il se capitalise ensuite au rendement
    jusqu'à la date d'évaluation, ce qui fait apparaître le coupon couru."""
    y = np.asarray(y, dtype=float) / 100
    c = np.asarray(coupon, dtype=float)
    n = T * f
    base = 1 + y / f
    with np.errstate(divide="ignore", invalid="ignore"):
        annuite = np.where(np.abs(y) > 1e-10, (1 - base ** (-n)) / (y / f), n)
    p = c / f * annuite + 100 * base ** (-n)
    return p * base ** (f * ecoule)


# ---------------------------------------------------------------------------- rendements quotidiens
def rendements_maturite_constante(courbe_eur, courbe_usd, positions, dates) -> dict:
    """Rendement quotidien en devise locale de chaque obligation à maturité constante.

    courbe_eur, courbe_usd : DataFrames (dates × maturités) en %. Renvoie {code: array de rendements},
    le premier élément étant nul."""
    delta = np.r_[0, np.diff(dates.values).astype("timedelta64[D]").astype(float)] / 365.0
    ne, nu = courbe_eur.columns.values.astype(float), courbe_usd.columns.values.astype(float)
    ze, yu = courbe_eur.to_numpy(), courbe_usd.to_numpy()
    out = {}
    for p in positions:
        if p.classe != "obligation":
            continue
        r = np.zeros(len(dates))
        if p.devise == "EUR":
            c = coupon_pair_eur(ze[:-1], ne, p.maturite, p.frequence)
            prix = np.array([prix_eur(ze[i + 1], ne, c[i], p.maturite, delta[i + 1], p.frequence) for i in range(len(dates) - 1)])
            r[1:] = prix / 100 - 1
        else:
            c = interpoler(yu[:-1], nu, p.maturite)
            y1 = interpoler_par_ligne(yu[1:], nu, np.maximum(p.maturite - delta[1:], 0.25))
            r[1:] = prix_actuariel(y1, c, p.maturite, p.frequence, delta[1:]) / 100 - 1
        out[p.code] = r
    return out


# ---------------------------------------------------------------------------- revalorisation sous scénarios
def pnl_obligation(position, courbe_jour: np.ndarray, noeuds, chocs: np.ndarray, horizon_jours: float = 1.0) -> np.ndarray:
    """Rendement (en devise locale) de l'obligation détenue aujourd'hui sous des chocs de courbe.

    courbe_jour : taux aux nœuds aujourd'hui (%) ; chocs : (scénarios × nœuds) en points de base.
    Revalorisation complète : on détient l'obligation au pair d'aujourd'hui et on la valorise à l'horizon
    sur la courbe choquée."""
    noeuds = np.asarray(noeuds, dtype=float)
    dt = horizon_jours * 7 / 5 / 365.0                       # jours ouvrés → années calendaires
    choquee = courbe_jour[None, :] + chocs / 100
    T, f = position.maturite, position.frequence
    if position.devise == "EUR":
        c = coupon_pair_eur(courbe_jour, noeuds, T, f)
        return prix_eur(choquee, noeuds, np.full(len(chocs), c), T, dt, f) / 100 - 1
    c = interpoler(courbe_jour, noeuds, T)
    y = interpoler(choquee, noeuds, max(T - dt, 0.25))
    return prix_actuariel(y, c, T, f, dt) / 100 - 1


def sensibilites(position, courbe_jour: np.ndarray, noeuds) -> dict:
    """Duration modifiée, convexité et PV01 (en % de la valeur de la position, pour +1 pb parallèle)."""
    chocs = np.array([[-1.0] * len(noeuds), [0.0] * len(noeuds), [1.0] * len(noeuds)])
    r = pnl_obligation(position, courbe_jour, noeuds, chocs, horizon_jours=0)
    p_bas, p0, p_haut = 1 + r
    duration = (p_bas - p_haut) / (2 * p0 * BP)
    convexite = (p_bas + p_haut - 2 * p0) / (p0 * BP ** 2)
    return {"duration": duration, "convexite": convexite, "pv01_pct": (p0 - p_haut) / p0 * 100}
