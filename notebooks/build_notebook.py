"""Génère risque_de_marche.ipynb (carnet Colab pas à pas). Lancer : python notebooks/build_notebook.py"""
import json
from pathlib import Path

C = [
("md", """# Tableau de bord du risque de marché d'une trésorerie en FCFA

**Auteur : Elisée Boco** · Master Banque-Finance, spécialisation Marchés Financiers et Finance d'Entreprise (CESAG)

Ce carnet refait toute l'étude, pas à pas, sur un portefeuille de trésorerie de 100 milliards de FCFA suivi chaque jour d'avril 2007 à octobre 2026 :

1. **valoriser** les obligations à partir des courbes de taux de la BCE et du Trésor américain ;
2. construire les **rendements en euros**, donc en francs CFA, et les facteurs de risque ;
3. calculer la **VaR et l'Expected Shortfall** avec six modèles ;
4. les **valider** (Kupiec, Christoffersen, feux tricolores de Bâle, Acerbi-Székely) et en retenir un par une règle fixée à l'avance ;
5. **décomposer** le risque, faire les **tests de résistance**, contrôler les **limites** et se demander s'il faut **couvrir le dollar** ;
6. produire le **classeur Excel**, le **rapport quotidien** et le **tableau de bord**.

**Utilisation :** menu *Exécution → Tout exécuter* (environ une minute), ou cellule par cellule avec Maj + Entrée."""),
("md", """## Étape 0 — Récupérer le projet

Le dépôt contient le code, les tests et les données figées le 30 octobre 2026 (dernière séance : 28 octobre)."""),
("code", """import os, sys
DEPOT = "https://github.com/Elisee-Boco/market-risk-dashboard.git"
if not os.path.exists("market-risk-dashboard"):
    !git clone -q {DEPOT}
%cd market-risk-dashboard
!pip install -q -r requirements.txt
sys.path.insert(0, os.getcwd())
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
pd.set_option("display.width", 200); pd.set_option("display.max_columns", 30)
from IPython.display import Image, display"""),
("md", """## Étape 1 — Vérifier le moteur

Vingt-trois tests sur des cas dont le résultat est connu : une obligation émise au pair vaut 100 ; la duration égale la formule fermée ; la PV01 explique la perte d'un choc de +1 pb ; les modèles retrouvent le quantile d'une loi normale ; le GARCH retrouve ses propres paramètres sur données simulées ; Christoffersen détecte des dépassements groupés ; la décomposition d'Euler redonne exactement l'ES total."""),
("code", """!python tests/test_risque.py"""),
("md", """## Étape 2 — Le portefeuille et les données

Allocation fixée à l'avance et rééquilibrée chaque jour. Valeur ramenée à 100 milliards de FCFA au 28 octobre 2026."""),
("code", """from src import donnees as dn, portefeuille as pf, obligations as ob
from src.parametres import POSITIONS, FCFA_PAR_EURO
m = dn.charger()
print("\\n".join(m["journal"]))
display(pd.DataFrame([{"position": p.libelle, "poids": p.poids, "devise": p.devise, "maturité": p.maturite} for p in POSITIONS]))
b = pf.construire(m)
display(((1 + b["r_eur"].iloc[1:]).groupby(b["dates"][1:].year).prod() - 1).mul(100).round(1).tail(8))"""),
("md", """### Valoriser une obligation à la main

Obligation d'État zone euro à 10 ans émise au pair sur la courbe zéro-coupon du 28 octobre 2026. On calcule son coupon, puis l'effet d'une hausse de 100 pb de toute la courbe : la perte est un peu inférieure à duration × 1 %, grâce à la convexité."""),
("code", """noeuds = b["eur"].columns.values.astype(float)
z = b["eur"].iloc[-1].to_numpy()
p10 = POSITIONS[3]
c = ob.coupon_pair_eur(z, noeuds, 10)
print(f"Taux zéro-coupon à 10 ans : {np.interp(10, noeuds, z):.3f} %, coupon au pair : {c:.3f} %")
s = ob.sensibilites(p10, z, noeuds)
print(f"Duration modifiée {s['duration']:.2f}, convexité {s['convexite']:.1f}")
r = ob.pnl_obligation(p10, z, noeuds, np.full((1, len(noeuds)), 100.0), horizon_jours=0)[0]
approx = -s["duration"] * 0.01 + 0.5 * s["convexite"] * 0.01 ** 2
print(f"Choc de +100 pb : {r * 100:.2f} % (revalorisation complète) contre {approx * 100:.2f} % (duration et convexité)")"""),
("md", """## Étape 3 — Les six modèles de VaR

Chaque soir, chaque modèle prévoit la perte du lendemain qui ne sera dépassée qu'une fois sur cent. Calcul de 4 751 prévisions (environ 20 secondes)."""),
("code", """from src import modeles_var as mv, backtest as bt
prev = mv.previsions(b)
dernier = prev.iloc[-1]
display(pd.DataFrame({mv.LIBELLES[k]: {"VaR 99 % (%)": dernier[f"{k}_var99"] * 100, "ES 97,5 % (%)": dernier[f"{k}_es975"] * 100,
                                         "VaR 99 % (M FCFA)": dernier[f"{k}_var99"] * 1e11 / 1e6} for k in mv.MODELES}).T.round(3))
print(f"GARCH du dernier jour : alpha = {dernier.garch_alpha:.3f}, beta = {dernier.garch_beta:.3f} ; Student : {dernier.student_nu:.1f} degrés de liberté")"""),
("md", """## Étape 4 — Valider les modèles

Un modèle à 99 % devrait être dépassé environ 48 fois sur 4 751 séances, à des dates indépendantes. On applique ensuite la règle de choix fixée à l'avance."""),
("code", """from src import pipeline as pl
ev = bt.evaluer(prev)
t = ev["tableau"]
display(t[["libelle", "depassements", "attendus", "p_pof", "p_ind", "p_cc", "part_vert", "part_rouge", "z2_es", "verdict_es", "var_moyenne", "rang_perte_quantile"]].round(3))
print("Modèle retenu :", mv.LIBELLES[pl.choisir_modele(t)])
display(bt.par_annee(prev))"""),
("md", """### Le test de Kupiec à la main

LR = −2 [ (n − x) ln(1 − p) + x ln p − (n − x) ln(1 − x/n) − x ln(x/n) ], qui suit un khi-deux à un degré de liberté."""),
("code", """from scipy import stats
n, x, p = len(prev) - 1, int(t.set_index("modele").loc["fhs", "depassements"]), 0.01
lr = -2 * ((n - x) * np.log(1 - p) + x * np.log(p) - (n - x) * np.log(1 - x / n) - x * np.log(x / n))
print(f"n = {n}, x = {x}, LR = {lr:.3f}, p-valeur = {stats.chi2.sf(lr, 1):.3f}")"""),
("md", """## Étape 5 — Toute l'analyse, et les figures"""),
("code", """res = pl.analyser()
pl.exporter(res)
for f in ["01_valeur_portefeuille", "02_var_et_rendements", "02b_var_2020", "04_zones_bale", "05_comparaison_modeles"]:
    display(Image(f"output/figures/{f}.png", width=950))"""),
("md", """### D'où vient le risque

L'ES par composante (Euler) dit quelle part des pertes des pires jours vient de chaque facteur ; la VaR paramétrique le dit avec les corrélations moyennes. L'écart entre les deux est le message."""),
("code", """display(res["decomposition"].round(4))
display(res["incrementale"].round(5))
display(Image("output/figures/06_decomposition.png", width=900))
display(Image("output/figures/07_decomposition_dans_le_temps.png", width=900))"""),
("md", """### Tests de résistance

Huit crises rejouées sur le portefeuille d'aujourd'hui (variations de facteurs pendant la crise, revalorisation complète), neuf scénarios hypothétiques, et le test inversé : par combien multiplier le scénario pour perdre 5 % ?"""),
("code", """s = res["resistance"]
display(s[["scenario", "type", "rendement", "rendement_vecu", "multiple_inverse"]].round(4))
display(Image("output/figures/08_tests_de_resistance.png", width=950))"""),
("md", """### Sensibilités, limites et couverture du dollar"""),
("code", """display(res["sensibilites"][["libelle", "poids", "taux", "duration", "convexite", "pv01_eur"]].round(3))
display(res["limites"].round(3))
display(res["couverture"].round(4))
for f in ["09_sensibilites", "12_limite_var", "13_couverture_dollar", "10_attribution", "11_monte_carlo_10_jours"]:
    display(Image(f"output/figures/{f}.png", width=900))"""),
("md", """## Étape 6 — Les livrables : classeur, rapport quotidien, tableau de bord

Le classeur contient une feuille où la VaR se recalcule par formules quand on change les poids. Le rapport quotidien tient sur une page. Le tableau de bord est une page web autonome."""),
("code", """from src import excel, rapport_quotidien as rq
excel.construire(res, pl.SORTIE / "Tableau_de_bord_risque_marche.xlsx")
rq.produire(res, pl.SORTIE)
sys.path.insert(0, "tableau_de_bord")
import construire
construire.construire(res)
import shutil
shutil.copy("tableau_de_bord/index.html", "output/tableau_de_bord.html")
shutil.make_archive("resultats_risque_marche", "zip", ".", "output")
try:
    from google.colab import files
    files.download("resultats_risque_marche.zip")
except ImportError:
    print("Fichier prêt : resultats_risque_marche.zip")"""),
]


def cellule(t, s):
    lignes = s.split("\n")
    src = [l + "\n" for l in lignes[:-1]] + [lignes[-1]]
    if t == "md":
        return {"cell_type": "markdown", "metadata": {}, "source": src}
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": src}


nb = {"cells": [cellule(t, s) for t, s in C],
      "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                   "language_info": {"name": "python"}, "colab": {"provenance": []}},
      "nbformat": 4, "nbformat_minor": 5}
out = Path(__file__).with_name("risque_de_marche.ipynb")
out.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
print(out)
