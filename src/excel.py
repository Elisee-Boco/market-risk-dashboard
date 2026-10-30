"""Classeur Excel de reporting des risques, avec une VaR recalculable par formules."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .analyses import MANCHES
from .modeles_var import LIBELLES, MODELES
from .parametres import FCFA_PAR_EURO, LIMITES, POSITIONS, VALEUR_FCFA

TITRE = Font(name="Calibri", size=14, bold=True, color="13213A")
SOUS = Font(name="Calibri", size=11, bold=True, color="13213A")
GRAS = Font(name="Calibri", size=10, bold=True)
NORMAL = Font(name="Calibri", size=10)
GRIS = Font(name="Calibri", size=9, italic=True, color="6A7280")
BLANC = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
ENTETE = PatternFill("solid", fgColor="13213A")
SAISIE = PatternFill("solid", fgColor="FFF4CC")
CALCUL = PatternFill("solid", fgColor="E8F1FB")
VERT = PatternFill("solid", fgColor="D5F0DD")
ORANGE = PatternFill("solid", fgColor="FCE8C8")
ROUGE = PatternFill("solid", fgColor="F8D3CF")
FIN = Side(style="thin", color="C3CCD9")
BORD = Border(top=FIN, bottom=FIN, left=FIN, right=FIN)


def _entetes(ws, ligne, noms, largeurs=None):
    for j, n in enumerate(noms, 1):
        c = ws.cell(ligne, j, n)
        c.font, c.fill, c.alignment = BLANC, ENTETE, Alignment(wrap_text=True, vertical="center")
        if largeurs:
            ws.column_dimensions[get_column_letter(j)].width = largeurs[j - 1]


def _table(ws, ligne, df: pd.DataFrame, colonnes, largeurs=None, formats=None):
    _entetes(ws, ligne, [c[1] for c in colonnes], largeurs)
    for i, (_, r) in enumerate(df.iterrows(), ligne + 1):
        for j, (col, _) in enumerate(colonnes, 1):
            v = r[col]
            if isinstance(v, (np.floating, float)) and (np.isnan(v) or np.isinf(v)):
                v = None
            if isinstance(v, pd.Timestamp):
                v = v.date()
            if isinstance(v, np.generic):
                v = v.item()
            c = ws.cell(i, j, v)
            c.font, c.border = NORMAL, BORD
            if formats and col in formats:
                c.number_format = formats[col]
    return ligne + len(df)


def _statut(ws, plage):
    ws.conditional_formatting.add(plage, CellIsRule(operator="equal", formula=['"vert"'], fill=VERT))
    ws.conditional_formatting.add(plage, CellIsRule(operator="equal", formula=['"orange"'], fill=ORANGE))
    ws.conditional_formatting.add(plage, CellIsRule(operator="equal", formula=['"rouge"'], fill=ROUGE))


def construire(res: dict, chemin: Path) -> Path:
    b = res["base"]
    date = res["date"].strftime("%d/%m/%Y")
    wb = Workbook()

    # ------------------------------------------------------------------ Lisez-moi
    ws = wb.active
    ws.title = "Lisez-moi"
    lignes = [
        ("Tableau de bord du risque de marché d'une trésorerie en FCFA", TITRE),
        (f"Elisée Boco · portefeuille de 100 milliards de FCFA · arrêté au {date}", GRIS),
        ("", NORMAL),
        ("Feuilles", SOUS),
        ("Rapport du jour : VaR et ES des six modèles, limites et tests de résistance, comme le rapport remis au comité des risques.", NORMAL),
        ("Portefeuille : positions, montants et sensibilités (duration, convexité, PV01).", NORMAL),
        ("VaR par formules : 250 séances de rendements et des poids modifiables (cellules jaunes). La VaR se recalcule seule.", NORMAL),
        ("Backtesting : synthèse des tests et test de Kupiec recalculé par formules.", NORMAL),
        ("Prévisions quotidiennes : la VaR de chaque modèle, le rendement du lendemain et les dépassements, 2008-2026.", NORMAL),
        ("Résistance, Décomposition, Couverture du dollar, Performance : les analyses de la note méthodologique.", NORMAL),
        ("", NORMAL),
        ("Conventions", SOUS),
        ("Valeurs en euros, converties en FCFA au taux fixe de 655,957 FCFA pour 1 €.", NORMAL),
        ("VaR et ES : pertes positives, en % de la valeur du portefeuille, horizon un jour sauf mention contraire.", NORMAL),
        ("Cellules jaunes : hypothèses modifiables. Cellules bleues : formules.", NORMAL),
        ("", NORMAL),
        ("Sources", SOUS),
        ("Trésor américain (courbe des taux au pair), BCE (courbe zéro-coupon AAA, taux de change de référence), Yahoo Finance (Euro Stoxx 50, S&P 500, or).", NORMAL),
    ]
    for i, (t, f) in enumerate(lignes, 1):
        ws.cell(i, 1, t).font = f
    ws.column_dimensions["A"].width = 130

    # ------------------------------------------------------------------ Rapport du jour
    ws = wb.create_sheet("Rapport du jour")
    ws["A1"], ws["A1"].font = f"Rapport de risque au {date}", TITRE
    ws["A2"], ws["A2"].font = f"Modèle de référence : {LIBELLES[res['retenu']]} (choisi par la règle fixée à l'avance, voir la note)", GRIS
    j = res["jour"].copy()
    for c in ("var99_1j", "es975_1j", "var99_10j_racine", "var99_10j_direct"):
        j[c + "_fcfa"] = j[c] * VALEUR_FCFA / 1e6
    ws["A4"], ws["A4"].font = "VaR et Expected Shortfall des six modèles", SOUS
    fin = _table(ws, 5, j, [("libelle", "Modèle"), ("var99_1j", "VaR 99 % 1 jour"), ("var99_1j_fcfa", "VaR 99 % 1 jour (M FCFA)"),
                           ("es975_1j", "ES 97,5 % 1 jour"), ("es975_1j_fcfa", "ES 97,5 % 1 jour (M FCFA)"),
                           ("var99_10j_racine", "VaR 99 % 10 jours (racine de 10)"), ("var99_10j_direct", "VaR 99 % 10 jours (directe)")],
                 [36, 14, 16, 14, 16, 18, 18],
                 {"var99_1j": "0.00%", "es975_1j": "0.00%", "var99_10j_racine": "0.00%", "var99_10j_direct": "0.00%",
                  "var99_1j_fcfa": "#,##0", "es975_1j_fcfa": "#,##0"})
    ligne = fin + 2
    ws.cell(ligne, 1, "Limites").font = SOUS
    lim = res["limites"]
    fin = _table(ws, ligne + 1, lim, [("libelle", "Indicateur"), ("valeur", "Valeur"), ("limite", "Limite"), ("utilisation", "Utilisation"), ("statut", "Statut")],
                 formats={"valeur": "0.000", "limite": "0.000", "utilisation": "0%"})
    _statut(ws, f"E{ligne + 2}:E{fin}")
    ligne = fin + 2
    ws.cell(ligne, 1, "Tests de résistance").font = SOUS
    s = res["resistance"].copy()
    s["perte_fcfa"] = s.perte_eur * FCFA_PAR_EURO / 1e9
    _table(ws, ligne + 1, s, [("scenario", "Scénario"), ("type", "Type"), ("rendement", "Effet sur le portefeuille"),
                              ("perte_fcfa", "Perte (Md FCFA)"), ("multiple_inverse", "Multiple pour perdre 5 %")],
           formats={"rendement": "0.00%", "perte_fcfa": "0.00", "multiple_inverse": "0.00"})

    # ------------------------------------------------------------------ Portefeuille
    ws = wb.create_sheet("Portefeuille")
    ws["A1"], ws["A1"].font = f"Positions et sensibilités au {date}", TITRE
    sens = res["sensibilites"].copy()
    sens["montant_fcfa"] = sens.montant_eur * FCFA_PAR_EURO / 1e9
    sens["pv01_fcfa"] = sens.pv01_eur * FCFA_PAR_EURO / 1e6
    _table(ws, 3, sens, [("libelle", "Position"), ("devise", "Devise"), ("poids", "Poids"), ("montant_fcfa", "Montant (Md FCFA)"),
                         ("taux", "Taux (%)"), ("duration", "Duration modifiée"), ("convexite", "Convexité"), ("pv01_fcfa", "PV01 (M FCFA)")],
           [36, 8, 9, 14, 10, 12, 11, 12],
           {"poids": "0.0%", "montant_fcfa": "0.00", "taux": "0.00", "duration": "0.00", "convexite": "0.0", "pv01_fcfa": "0.00"})

    # ------------------------------------------------------------------ VaR par formules
    ws = wb.create_sheet("VaR par formules")
    ws["A1"], ws["A1"].font = "VaR normale et historique recalculées par formules sur les 250 dernières séances", TITRE
    ws["A2"], ws["A2"].font = ("Modifiez les poids en jaune (leur somme doit faire 100 %) : la VaR se recalcule. Simulation historique sur les "
                               "rendements (sans revalorisation complète des obligations), d'où un léger écart avec le moteur Python."), GRIS
    codes = [p.code for p in POSITIONS]
    r = b["r_eur"].iloc[-250:]
    ws.cell(4, 1, "Poids").font = GRAS
    ws.cell(5, 1, "Position").font = GRAS
    for k, p in enumerate(POSITIONS, 2):
        c = ws.cell(4, k, p.poids)
        c.fill, c.number_format, c.border = SAISIE, "0.0%", BORD
        ws.cell(5, k, p.libelle).font = GRAS
        ws.cell(5, k).alignment = Alignment(wrap_text=True)
        ws.column_dimensions[get_column_letter(k)].width = 13
    kp = len(POSITIONS) + 2
    lp = get_column_letter(kp)
    ws.cell(5, kp, "Portefeuille").font = GRAS
    ws.cell(4, kp, f"=SUM(B4:{get_column_letter(kp - 1)}4)").number_format = "0.0%"
    ws.column_dimensions["A"].width = 12
    for i, (d, row) in enumerate(r.iterrows(), 6):
        ws.cell(i, 1, d.date()).number_format = "yyyy-mm-dd"
        for k, c in enumerate(codes, 2):
            ws.cell(i, k, float(row[c])).number_format = "0.000%"
        ws.cell(i, kp, f"=SUMPRODUCT($B$4:${get_column_letter(kp - 1)}$4,B{i}:{get_column_letter(kp - 1)}{i})").number_format = "0.000%"
    der = 5 + len(r)
    k0 = kp + 2
    col = get_column_letter(k0 + 1)
    ws.column_dimensions[get_column_letter(k0)].width = 38
    ws.column_dimensions[col].width = 16
    rows = [
        ("Valeur du portefeuille (FCFA)", VALEUR_FCFA, "#,##0", True),
        ("Niveau de confiance", 0.99, "0.0%", True),
        ("Écart-type quotidien", f"=_xlfn.STDEV.S({lp}6:{lp}{der})", "0.000%", False),
        ("VaR normale (% de la valeur)", f"=_xlfn.NORM.S.INV({col}5)*{col}6", "0.000%", False),
        ("VaR normale (FCFA)", f"={col}7*{col}4", "#,##0", False),
        ("VaR historique sur 250 séances (%)", f"=-_xlfn.PERCENTILE.INC({lp}6:{lp}{der},1-{col}5)", "0.000%", False),
        ("VaR historique (FCFA)", f"={col}9*{col}4", "#,##0", False),
        ("ES normale à 97,5 % (%)", f"={col}6*EXP(-(_xlfn.NORM.S.INV(0.975)^2)/2)/SQRT(2*PI())/0.025", "0.000%", False),
        ("VaR normale à 10 jours (racine de 10, %)", f"={col}7*SQRT(10)", "0.000%", False),
    ]
    for k, (lab, v, fmt, saisie) in enumerate(rows, 4):
        ws.cell(k, k0, lab).font = GRAS
        c = ws.cell(k, k0 + 1, v)
        c.number_format, c.fill, c.border = fmt, SAISIE if saisie else CALCUL, BORD

    # ------------------------------------------------------------------ Backtesting
    ws = wb.create_sheet("Backtesting")
    ws["A1"], ws["A1"].font = "Validation a posteriori des modèles, 2008 – 2026", TITRE
    t = res["backtest"]["tableau"]
    fin = _table(ws, 3, t, [("libelle", "Modèle"), ("depassements", "Dépassements"), ("attendus", "Attendus"), ("taux", "Taux"),
                            ("p_pof", "p Kupiec"), ("p_ind", "p indépendance"), ("p_cc", "p couverture conditionnelle"),
                            ("part_vert", "Séances en zone verte"), ("part_rouge", "Séances en zone rouge"), ("z2_es", "Z2 (ES)"),
                            ("verdict_es", "Verdict ES"), ("var_moyenne", "VaR moyenne"), ("perte_quantile", "Perte quantile"),
                            ("rang_perte_quantile", "Rang")],
                 [36, 12, 10, 9, 10, 12, 13, 12, 12, 9, 10, 11, 12, 7],
                 {"attendus": "0.0", "taux": "0.00%", "p_pof": "0.000", "p_ind": "0.000", "p_cc": "0.000", "part_vert": "0%",
                  "part_rouge": "0%", "z2_es": "0.00", "var_moyenne": "0.000%", "perte_quantile": "0.000000"})
    _statut(ws, f"K4:K{fin}")
    l0 = fin + 3
    ws.cell(l0, 1, "Test de Kupiec par formules").font = SOUS
    ws.cell(l0 + 1, 1, "Séances").font = GRAS
    ws.cell(l0 + 2, 1, "Dépassements").font = GRAS
    ws.cell(l0 + 3, 1, "Probabilité attendue").font = GRAS
    ws.cell(l0 + 4, 1, "Statistique LR").font = GRAS
    ws.cell(l0 + 5, 1, "p-valeur (khi-deux, 1 ddl)").font = GRAS
    retenu = t[t.modele == res["retenu"]].iloc[0]
    for k, v in ((1, int(retenu.n)), (2, int(retenu.depassements)), (3, 0.01)):
        c = ws.cell(l0 + k, 2, v)
        c.fill, c.border = SAISIE, BORD
    n, x, p = f"B{l0 + 1}", f"B{l0 + 2}", f"B{l0 + 3}"
    ws.cell(l0 + 4, 2, f"=-2*(({n}-{x})*LN(1-{p})+{x}*LN({p})-({n}-{x})*LN(1-{x}/{n})-{x}*LN({x}/{n}))").fill = CALCUL
    ws.cell(l0 + 5, 2, f"=_xlfn.CHISQ.DIST.RT(B{l0 + 4},1)").fill = CALCUL
    ws.cell(l0 + 4, 2).number_format = ws.cell(l0 + 5, 2).number_format = "0.000"
    ws.cell(l0 + 6, 1, "Rejet au seuil de 5 % si p < 0,05. Valeurs pré-remplies : modèle de référence.").font = GRIS

    # ------------------------------------------------------------------ Prévisions quotidiennes
    ws = wb.create_sheet("Prévisions quotidiennes")
    pr = res["previsions"].dropna(subset=["rendement_suivant"]).copy()
    cols = ["rendement_suivant"] + [f"{m}_var99" for m in MODELES]
    noms = ["Date", "Rendement du lendemain"] + [f"VaR 99 % {LIBELLES[m]}" for m in MODELES] + [f"Dépassement {m}" for m in MODELES]
    _entetes(ws, 1, noms, [12, 12] + [14] * len(MODELES) + [10] * len(MODELES))
    for i, (d, row) in enumerate(pr.iterrows(), 2):
        ws.cell(i, 1, d.date()).number_format = "yyyy-mm-dd"
        for k, c in enumerate(cols, 2):
            ws.cell(i, k, float(row[c])).number_format = "0.000%"
        for k, m in enumerate(MODELES):
            cv = get_column_letter(3 + k)
            ws.cell(i, 3 + len(MODELES) + k, f"=IF(B{i}<-{cv}{i},1,0)")
    ws.freeze_panes = "B2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(noms))}{len(pr) + 1}"

    # ------------------------------------------------------------------ Analyses
    def feuille(nom, titre, df, colonnes, formats=None, largeurs=None):
        w = wb.create_sheet(nom)
        w["A1"], w["A1"].font = titre, TITRE
        _table(w, 3, df, colonnes, largeurs, formats)
        return w

    s = res["resistance"]
    feuille("Résistance", f"Tests de résistance sur le portefeuille du {date}", s,
            [("scenario", "Scénario"), ("type", "Type"), ("debut", "Début"), ("fin", "Fin"), ("rendement", "Effet total")]
            + [(f"c_{m}", m) for m in MANCHES] + [("rendement_vecu", "Rendement vécu par le portefeuille"), ("multiple_inverse", "Multiple pour perdre 5 %")],
            {**{"rendement": "0.00%", "rendement_vecu": "0.00%", "multiple_inverse": "0.00"}, **{f"c_{m}": "0.00%" for m in MANCHES}},
            [48, 12, 11, 11, 11] + [12] * len(MANCHES) + [14, 12])
    feuille("Décomposition", f"D'où vient le risque au {date}", res["decomposition"],
            [("manche", "Facteur"), ("es_composante", "ES par composante"), ("part_es", "Part de l'ES"),
             ("var_composante_param", "VaR paramétrique par composante"), ("part_var_param", "Part de la VaR paramétrique"),
             ("var_autonome_hs", "VaR du facteur seul")],
            {"es_composante": "0.000%", "part_es": "0%", "var_composante_param": "0.000%", "part_var_param": "0%", "var_autonome_hs": "0.000%"},
            [22, 14, 12, 16, 16, 14])
    feuille("Couverture du dollar", "Effet d'une couverture à terme d'une part de l'exposition en dollars, 2007 – 2026", res["couverture"],
            [("ratio", "Part couverte"), ("cagr", "Rendement annuel"), ("volatilite", "Volatilité"), ("baisse_max", "Baisse maximale"),
             ("pire_jour", "Pire jour"), ("var99_hs_jour", "VaR 99 % du jour (historique)"), ("es975_hs_jour", "ES 97,5 % du jour"),
             ("cout_portage_annuel", "Portage de la couverture par an")],
            {"ratio": "0%", "cagr": "0.00%", "volatilite": "0.00%", "baisse_max": "0.00%", "pire_jour": "0.00%",
             "var99_hs_jour": "0.000%", "es975_hs_jour": "0.000%", "cout_portage_annuel": "0.00%"}, [12] * 8)
    ann = res["annuels"].reset_index().rename(columns={"index": "annee"})
    ann.columns = ["annee"] + list(ann.columns[1:])
    lib = {p.code: p.libelle for p in POSITIONS}
    w = feuille("Performance", "Rendements annuels en euros (donc en FCFA) de chaque position et du portefeuille", ann,
                [("annee", "Année")] + [(c, lib.get(c, "Portefeuille")) for c in ann.columns[1:]],
                {c: "0.0%" for c in ann.columns[1:]}, [8] + [13] * (len(ann.columns) - 1))
    a = res["attribution"].reset_index()
    a.columns = ["annee"] + list(a.columns[1:])
    for c in a.columns[1:]:
        a[c] = a[c] * FCFA_PAR_EURO / 1e9
    w2 = wb.create_sheet("Attribution")
    w2["A1"], w2["A1"].font = "Contribution de chaque facteur au gain annuel (milliards de FCFA)", TITRE
    _table(w2, 3, a, [("annee", "Année")] + [(c, c) for c in a.columns[1:]], [8] + [14] * (len(a.columns) - 1),
           {c: "0.00" for c in a.columns[1:]})
    wb.save(chemin)
    return chemin
