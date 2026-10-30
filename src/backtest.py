"""Validation a posteriori (backtesting) des modèles de VaR et d'ES.

  - Kupiec (1995) : la fréquence des dépassements est-elle égale à 1 % ? Test du rapport de vraisemblance,
    LR_pof suit un khi-deux à 1 degré de liberté.
  - Christoffersen (1998) : les dépassements arrivent-ils en grappes ? LR_ind (indépendance, chaîne de
    Markov d'ordre 1) et LR_cc = LR_pof + LR_ind (couverture conditionnelle, 2 degrés de liberté).
  - Feux tricolores du Comité de Bâle (1996) : nombre de dépassements sur les 250 dernières séances ;
    vert de 0 à 4, orange de 5 à 9, rouge à partir de 10.
  - Acerbi et Székely (2014), statistique Z2 pour l'Expected Shortfall : nulle en moyenne si l'ES est juste,
    négative s'il sous-estime les pertes ; seuils de 0,70 (orange) et 1,80 (rouge).
  - Fonction de perte quantile (« tick loss ») pour classer les modèles : plus elle est faible, mieux la VaR
    suit le vrai quantile (Giacomini et Komunjer, 2005).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from .modeles_var import LIBELLES, MODELES
from .parametres import NIVEAU_ES, NIVEAU_VAR

SEUILS_BALE = (4, 9)
SEUILS_Z2 = (-0.70, -1.80)


def _xlogy(x, y):
    return 0.0 if x == 0 else x * np.log(y)


def kupiec(n_dep: int, n: int, p: float = 1 - NIVEAU_VAR) -> dict:
    pi = n_dep / n
    lr = -2 * (_xlogy(n - n_dep, 1 - p) + _xlogy(n_dep, p) - _xlogy(n - n_dep, 1 - pi) - _xlogy(n_dep, pi))
    return {"lr_pof": lr, "p_pof": float(stats.chi2.sf(lr, 1))}


def christoffersen(i: np.ndarray, p: float = 1 - NIVEAU_VAR) -> dict:
    i = np.asarray(i, dtype=int)
    a, b = i[:-1], i[1:]
    n00, n01 = int(((a == 0) & (b == 0)).sum()), int(((a == 0) & (b == 1)).sum())
    n10, n11 = int(((a == 1) & (b == 0)).sum()), int(((a == 1) & (b == 1)).sum())
    p01 = n01 / max(n00 + n01, 1)
    p11 = n11 / max(n10 + n11, 1)
    p1 = (n01 + n11) / max(n00 + n01 + n10 + n11, 1)
    l1 = _xlogy(n00, 1 - p01) + _xlogy(n01, p01) + _xlogy(n10, 1 - p11) + _xlogy(n11, p11)
    l0 = _xlogy(n00 + n10, 1 - p1) + _xlogy(n01 + n11, p1)
    lr_ind = -2 * (l0 - l1)
    lr_pof = kupiec(int(i.sum()), len(i), p)["lr_pof"]
    return {"lr_ind": lr_ind, "p_ind": float(stats.chi2.sf(lr_ind, 1)), "lr_cc": lr_pof + lr_ind,
            "p_cc": float(stats.chi2.sf(lr_pof + lr_ind, 2)), "dep_consecutifs": n11, "p_apres_depassement": p11}


def zone_bale(n_dep_250: int) -> str:
    return "vert" if n_dep_250 <= SEUILS_BALE[0] else ("orange" if n_dep_250 <= SEUILS_BALE[1] else "rouge")


def acerbi_szekely_z2(x: np.ndarray, var975: np.ndarray, es975: np.ndarray, alpha: float = 1 - NIVEAU_ES) -> float:
    """Z2 = somme(X_t · I_t / (T · alpha · ES_t)) + 1, avec X_t le rendement, I_t = 1 si X_t < −VaR_t."""
    i = x < -var975
    return float(np.sum(x * i / (len(x) * alpha * es975)) + 1)


def perte_quantile(x: np.ndarray, var: np.ndarray, p: float = 1 - NIVEAU_VAR) -> float:
    q = -var
    return float(np.mean((p - (x < q)) * (x - q)))


def evaluer(prev: pd.DataFrame) -> dict:
    """Tableau de synthèse par modèle, séries de dépassements et zones de Bâle glissantes."""
    prev = prev.dropna(subset=["rendement_suivant"])
    x = prev["rendement_suivant"].to_numpy()
    n = len(x)
    lignes, depassements, zones = [], {}, {}
    for m in MODELES:
        var = prev[f"{m}_var99"].to_numpy()
        i = (x < -var).astype(int)
        depassements[m] = pd.Series(i, index=prev.index)
        glissant = pd.Series(i, index=prev.index).rolling(250).sum()
        zones[m] = glissant
        z = glissant.dropna().astype(int).map(zone_bale)
        k = kupiec(int(i.sum()), n)
        c = christoffersen(i)
        z2 = acerbi_szekely_z2(x, prev[f"{m}_var975"].to_numpy(), prev[f"{m}_es975"].to_numpy())
        lignes.append({
            "modele": m, "libelle": LIBELLES[m], "n": n, "depassements": int(i.sum()), "attendus": n * (1 - NIVEAU_VAR),
            "taux": i.mean(), **k, **c,
            "z2_es": z2, "verdict_es": "vert" if z2 > SEUILS_Z2[0] else ("orange" if z2 > SEUILS_Z2[1] else "rouge"),
            "var_moyenne": var.mean(), "es_moyen": prev[f"{m}_es975"].mean(),
            "perte_quantile": perte_quantile(x, var),
            "part_vert": (z == "vert").mean(), "part_orange": (z == "orange").mean(), "part_rouge": (z == "rouge").mean(),
            "max_dep_250": int(glissant.max()),
            "perte_moyenne_si_depassement": -x[i == 1].mean() if i.sum() else np.nan,
            "depassement_moyen_au_dela_var": (-x[i == 1] - var[i == 1]).mean() if i.sum() else np.nan,
        })
    t = pd.DataFrame(lignes)
    t["rang_perte_quantile"] = t.perte_quantile.rank().astype(int)
    return {"tableau": t, "depassements": pd.DataFrame(depassements), "glissant_250": pd.DataFrame(zones)}


def par_annee(prev: pd.DataFrame) -> pd.DataFrame:
    prev = prev.dropna(subset=["rendement_suivant"])
    x = prev["rendement_suivant"]
    d = {m: (x < -prev[f"{m}_var99"]).groupby(prev.index.year).sum() for m in MODELES}
    d = pd.DataFrame(d)
    d["seances"] = x.groupby(prev.index.year).size()
    return d
