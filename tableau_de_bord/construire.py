"""Construit tableau_de_bord/index.html : le gabarit et les résultats, en un seul fichier autonome.

Lancer après main.py (qui l'appelle aussi) : python tableau_de_bord/construire.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

from src.analyses import MANCHES  # noqa: E402
from src.modeles_var import LIBELLES, MODELES  # noqa: E402
from src.parametres import FCFA_PAR_EURO, LIMITES, POSITIONS, VALEUR_FCFA  # noqa: E402


def _r(x, n=4):
    if x is None:
        return None
    x = float(x)
    return None if (np.isnan(x) or np.isinf(x)) else round(x, n)


def _liste(s, n=4):
    return [_r(v, n) for v in s]


def _records(df, cols, n=5):
    out = []
    for _, r in df.iterrows():
        d = {}
        for c in cols:
            v = r[c]
            if isinstance(v, (float, np.floating, int, np.integer)) and not isinstance(v, bool):
                d[c] = _r(v, n)
            elif isinstance(v, pd.Timestamp):
                d[c] = v.strftime("%Y-%m-%d")
            else:
                d[c] = None if v is None or (isinstance(v, float) and np.isnan(v)) else str(v)
        out.append(d)
    return out


def donnees(res):
    p = res["previsions"]
    b = res["base"]
    g = res["backtest"]["glissant_250"].reindex(p.index).ffill(limit=1)      # dernière séance : compte de la veille
    v = b["valeur"].reindex(p.index) * FCFA_PAR_EURO / 1e9
    dd = (b["valeur"] / b["valeur"].cummax() - 1).reindex(p.index) * 100
    h = res["historique_mensuel"]
    t = res["backtest"]["tableau"]
    return {
        "date": res["date"].strftime("%Y-%m-%d"), "retenu": res["retenu"], "modeles": MODELES, "libelles": LIBELLES,
        "valeur_fcfa": VALEUR_FCFA, "limites": LIMITES, "manches": MANCHES,
        "dates": [d.strftime("%Y-%m-%d") for d in p.index],
        "r": _liste(p.rendement_suivant * 100, 4),
        "var": {m: _liste(p[f"{m}_var99"] * 100, 4) for m in MODELES},
        "es": {m: _liste(p[f"{m}_es975"] * 100, 4) for m in MODELES},
        "bale": {m: [None if np.isnan(x) else int(x) for x in g[m]] for m in MODELES},
        "valeur": _liste(v, 3), "baisse": _liste(dd, 3),
        "mois": [d.strftime("%Y-%m-%d") for d in h.index], "parts": {c: _liste(h[c], 4) for c in MANCHES},
        "backtest": _records(t, ["modele", "libelle", "depassements", "attendus", "taux", "p_pof", "p_ind", "p_cc", "z2_es", "verdict_es",
                                 "var_moyenne", "perte_quantile", "rang_perte_quantile", "part_vert", "part_orange", "part_rouge", "max_dep_250"], 6),
        "par_annee": {"annees": [int(a) for a in res["par_annee"].index], **{m: [int(x) for x in res["par_annee"][m]] for m in MODELES},
                      "seances": [int(x) for x in res["par_annee"].seances]},
        "jour": _records(res["jour"], ["modele", "libelle", "var99_1j", "es975_1j", "var99_10j_racine", "var99_10j_direct", "es975_10j_direct"], 6),
        "limites_jour": _records(res["limites"], ["indicateur", "libelle", "valeur", "limite", "utilisation", "statut"], 5),
        "resistance": _records(res["resistance"], ["code", "scenario", "type", "debut", "fin", "rendement", "perte_eur", "rendement_vecu", "multiple_inverse"]
                               + [f"c_{m}" for m in MANCHES], 5),
        "sensibilites": _records(res["sensibilites"], ["position", "libelle", "classe", "devise", "poids", "montant_eur", "taux", "duration", "convexite", "pv01_eur"], 5),
        "couverture": _records(res["couverture"], list(res["couverture"].columns), 5),
        "decomposition": _records(res["decomposition"], ["manche", "part_es", "part_var_param", "es_composante"], 5),
        "performance": {k: (v.strftime("%Y-%m-%d") if isinstance(v, pd.Timestamp) else _r(v, 5) if isinstance(v, (float, np.floating, int, np.integer)) else v)
                        for k, v in res["performance"].items()},
        "positions": [{"code": q.code, "libelle": q.libelle, "poids": q.poids, "devise": q.devise} for q in POSITIONS],
        "fcfa_par_euro": FCFA_PAR_EURO,
    }


def construire(res):
    d = donnees(res)
    gabarit = (RACINE / "tableau_de_bord" / "gabarit.html").read_text(encoding="utf-8")
    html = gabarit.replace("/*__DONNEES__*/null", json.dumps(d, ensure_ascii=False, separators=(",", ":")))
    sortie = RACINE / "tableau_de_bord" / "index.html"
    sortie.write_text(html, encoding="utf-8")
    print(sortie, f"{len(html) / 1024:.0f} Ko")
    return sortie


if __name__ == "__main__":
    from src import pipeline as pl
    construire(pl.analyser())
