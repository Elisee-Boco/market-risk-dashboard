"""Lance toute la chaîne : python main.py (environ une minute)."""
from src import excel, pipeline as pl, rapport_quotidien as rq

if __name__ == "__main__":
    res = pl.analyser(verbeux=True)
    print("\n".join(res["journal"]))
    print("Modèle de référence retenu par la règle :", res["retenu"])
    dossier = pl.exporter(res)
    excel.construire(res, dossier / "Tableau_de_bord_risque_marche.xlsx")
    rq.produire(res, dossier)
    try:
        import sys
        sys.path.insert(0, str(pl.RACINE / "tableau_de_bord"))
        import construire
        construire.construire(res)
    except Exception as e:
        print("Tableau de bord non reconstruit :", e)
    print(f"Résultats écrits dans {dossier} ({res['duree']:.0f} s d'analyse)")
