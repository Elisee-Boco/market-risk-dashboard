"""Chaîne complète : données, VaR, backtesting, décomposition, résistance, limites, performance."""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from . import analyses as an
from . import backtest as bt
from . import donnees as dn
from . import modeles_var as mv
from . import portefeuille as pf
from .parametres import FCFA_PAR_EURO, LIMITES, POSITIONS, SEUIL_VIGILANCE, VALEUR_EUR, VALEUR_FCFA

RACINE = Path(__file__).resolve().parents[1]
SORTIE = RACINE / "output"


def choisir_modele(t: pd.DataFrame) -> str:
    """Règle de choix fixée à l'avance : parmi les modèles qui passent le test de Kupiec à 5 %, ne sont jamais
    en zone rouge de Bâle et dont l'ES passe le test d'Acerbi-Székely, celui de plus faible perte quantile."""
    ok = t[(t.p_pof > 0.05) & (t.part_rouge == 0) & (t.verdict_es == "vert")]
    pool = ok if len(ok) else t
    return pool.sort_values("perte_quantile").modele.iloc[0]


def analyser(dossier=None, verbeux=False) -> dict:
    t0 = time.time()
    m = dn.charger(dossier) if dossier else dn.charger()
    base = pf.construire(m)
    prev = mv.previsions(base, verbeux=verbeux)
    ev = bt.evaluer(prev)
    retenu = choisir_modele(ev["tableau"])
    i = len(base["dates"]) - 1
    jour = mv.tableau_du_jour(base, prev, i)
    p_jour = prev.iloc[-1]
    sens = an.sensibilites(base, i)
    res = {
        "journal": m["journal"], "base": base, "previsions": prev, "backtest": ev, "par_annee": bt.par_annee(prev),
        "retenu": retenu, "jour": jour, "decomposition": an.decomposition(base, i), "incrementale": an.var_sans_position(base, i),
        "sensibilites": sens, "resistance": an.tests_resistance(base, i),
        "limites": an.limites(base, i, p_jour[f"{retenu}_var99"], p_jour[f"{retenu}_es975"], sens),
        "performance": an.performance(base), "attribution": an.attribution(base), "annuels": an.rendements_annuels(base),
        "mc_distribution": mv.monte_carlo(base, i, 1), "date": base["dates"][i], "couverture": an.couverture(base, i),
    }
    # Historique mensuel de la décomposition et des sensibilités (fin de mois)
    fins = base["r_p"].groupby(base["dates"].to_period("M")).tail(1).index
    fins = [d for d in fins if base["dates"].get_loc(d) >= mv.MINIMUM]
    hist = []
    for d in fins:
        k = base["dates"].get_loc(d)
        dec = an.decomposition(base, k)
        s = an.sensibilites(base, k)
        hist.append({"date": d, **dict(zip(dec.manche, dec.part_es)), "es": dec.attrs["es_total"],
                     "pv01_eur": s[s.devise == "EUR"].pv01_pct_portefeuille.sum(), "pv01_usd": s[s.devise == "USD"].pv01_pct_portefeuille.sum()})
    res["historique_mensuel"] = pd.DataFrame(hist).set_index("date")
    # Utilisation de la limite de VaR dans le temps (modèle retenu)
    u = prev[f"{retenu}_var99"] * 100 / LIMITES["var99_1j"]
    res["utilisation_var"] = u
    res["duree"] = time.time() - t0
    return res


def _json(x):
    if isinstance(x, (pd.Timestamp,)):
        return x.strftime("%Y-%m-%d")
    if isinstance(x, (np.floating, np.integer)):
        return x.item()
    if isinstance(x, float) and (np.isinf(x) or np.isnan(x)):
        return None
    return str(x)


def exporter(res: dict, dossier: Path = SORTIE) -> Path:
    from . import graphiques as gr
    t = dossier / "tables"
    t.mkdir(parents=True, exist_ok=True)
    res["previsions"].to_csv(t / "previsions_var.csv", index_label="date")
    res["backtest"]["tableau"].to_csv(t / "backtest.csv", index=False)
    res["par_annee"].to_csv(t / "depassements_par_annee.csv", index_label="annee")
    for k in ("jour", "decomposition", "incrementale", "sensibilites", "resistance", "limites", "couverture"):
        res[k].to_csv(t / f"{k}.csv", index=False)
    res["attribution"].to_csv(t / "attribution_eur.csv", index_label="annee")
    res["annuels"].to_csv(t / "rendements_annuels.csv", index_label="annee")
    res["historique_mensuel"].to_csv(t / "historique_mensuel.csv", index_label="date")
    b = res["base"]
    pd.DataFrame({"rendement": b["r_p"], "valeur_eur": b["valeur"], "valeur_fcfa": b["valeur"] * FCFA_PAR_EURO}).to_csv(t / "portefeuille_quotidien.csv", index_label="date")
    resume = {
        "date_arrete": res["date"], "journal": res["journal"], "modele_retenu": res["retenu"],
        "valeur_fcfa": VALEUR_FCFA, "valeur_eur": VALEUR_EUR, "performance": res["performance"],
        "decomposition": res["decomposition"].attrs, "duree_s": res["duree"],
        "positions": [{"code": p.code, "libelle": p.libelle, "poids": p.poids} for p in POSITIONS],
    }
    (dossier / "resultats.json").write_text(json.dumps(resume, indent=2, ensure_ascii=False, default=_json))
    gr.tout(res, dossier / "figures")
    return dossier
