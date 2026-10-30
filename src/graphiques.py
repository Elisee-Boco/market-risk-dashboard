"""Graphiques de la note et du tableau de bord (PNG, 200 dpi)."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd

from . import modeles_var as mv
from .analyses import MANCHES
from .parametres import FCFA_PAR_EURO, LIMITES, NIVEAU_ES

PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
C_MODELE = dict(zip(mv.MODELES + ["mc"], PALETTE))
C_MANCHE = dict(zip(MANCHES, PALETTE))
ENCRE, ENCRE_2, ENCRE_3 = "#0b0b0b", "#52514e", "#898781"
GRILLE, AXE, FOND = "#e1e0d9", "#c3c2b7", "#fcfcfb"
ROUGE, ORANGE, VERT = "#c0392b", "#d68910", "#1e8449"
COURT = {"hs": "Historique", "normale": "Normale", "student": "Student", "ewma": "EWMA", "fhs": "FHS (GARCH)", "mc": "Monte-Carlo"}

plt.rcParams.update({
    "figure.facecolor": FOND, "axes.facecolor": FOND, "savefig.facecolor": FOND,
    "axes.edgecolor": AXE, "axes.labelcolor": ENCRE_2, "axes.titlecolor": ENCRE,
    "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "axes.labelsize": 9.5, "xtick.color": ENCRE_3, "ytick.color": ENCRE_3,
    "xtick.labelsize": 8.5, "ytick.labelsize": 8.5, "axes.grid": True, "grid.color": GRILLE,
    "grid.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False,
    "legend.frameon": False, "legend.fontsize": 8.5, "font.size": 9.5,
    "font.family": "DejaVu Sans", "lines.linewidth": 1.6,
})


def _fr(d=0, suffixe=""):
    return mtick.FuncFormatter(lambda v, _: f"{v:.{d}f}".replace(".", ",").replace("-", "−") + suffixe)


def _sauver(fig, dossier: Path, nom: str) -> Path:
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / f"{nom}.png"
    fig.savefig(chemin, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return chemin


def _titre(fig, titre, sous_titre=None):
    fig.suptitle(titre, x=0.01, ha="left", fontweight="bold", fontsize=12.5, y=1.02)
    if sous_titre:
        fig.text(0.01, 0.975, sous_titre, ha="left", fontsize=9, color=ENCRE_2, va="top")


def valeur(res, d):
    b = res["base"]
    v = b["valeur"] * FCFA_PAR_EURO / 1e9
    dd = (b["valeur"] / b["valeur"].cummax() - 1) * 100
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(10, 5.6), sharex=True, gridspec_kw={"height_ratios": [2.2, 1], "hspace": 0.12})
    a1.plot(v.index, v, color=PALETTE[0])
    a1.yaxis.set_major_formatter(_fr(0, " Md"))
    a1.set_ylabel("Valeur (milliards de FCFA)")
    p = res["performance"]
    a1.text(0.01, 0.95, f"{p['cagr'] * 100:.2f} % par an, volatilité {p['volatilite'] * 100:.1f} %, Sharpe {p['sharpe']:.2f}".replace(".", ","),
            transform=a1.transAxes, va="top", fontsize=9, color=ENCRE_2)
    a2.fill_between(dd.index, dd, 0, color=PALETTE[1], alpha=0.35, lw=0)
    a2.plot(dd.index, dd, color=PALETTE[1], lw=1)
    a2.yaxis.set_major_formatter(_fr(0, " %"))
    a2.set_ylabel("Baisse depuis\nle plus haut")
    i = dd.idxmin()
    a2.annotate(f"{dd.min():.1f} %".replace(".", ",").replace("-", "−"), (i, dd.min()), xytext=(8, 4), textcoords="offset points", fontsize=8.5, color=ENCRE_2)
    _titre(fig, "Le portefeuille de trésorerie, avril 2007 – octobre 2026",
           "Allocation fixe rééquilibrée chaque jour ; valeur ramenée à 100 milliards de FCFA au 28 octobre 2026")
    return _sauver(fig, d, "01_valeur_portefeuille")


def var_et_rendements(res, d, debut=None, fin=None, nom="02_var_et_rendements", titre=None):
    p = res["previsions"].dropna(subset=["rendement_suivant"])
    if debut:
        p = p.loc[debut:fin]
    x = p.rendement_suivant * 100
    idx = p.index
    fig, ax = plt.subplots(figsize=(10, 4.6))
    ax.vlines(idx, 0, x, color=ENCRE_3 if not debut else AXE, lw=0.5 if not debut else 2.2, alpha=0.6, label="Rendement du lendemain")
    for m in mv.MODELES:
        ax.plot(idx, -p[f"{m}_var99"] * 100, color=C_MODELE[m], lw=1.2 if m == res["retenu"] else 0.8,
                alpha=1 if m == res["retenu"] else 0.75, label=f"VaR 99 % : {COURT[m]}")
    r = res["retenu"]
    dep = x < -p[f"{r}_var99"] * 100
    ax.scatter(idx[dep], x[dep], s=14 if debut else 9, color=ROUGE, zorder=4, label=f"Dépassement ({COURT[r]})")
    ax.yaxis.set_major_formatter(_fr(1, " %"))
    ax.legend(ncol=4, loc="lower left", bbox_to_anchor=(0, 1.0), fontsize=8)
    ax.set_title(titre or "Six modèles, un seul portefeuille : la VaR suit la volatilité, avec plus ou moins de retard", pad=34)
    return _sauver(fig, d, nom)


def depassements_annuels(res, d):
    a = res["par_annee"]
    fig, ax = plt.subplots(figsize=(10, 3.8))
    larg = 0.16
    x = np.arange(len(a))
    for k, m in enumerate(mv.MODELES):
        ax.bar(x + (k - 2) * larg, a[m], width=larg, color=C_MODELE[m], label=COURT[m])
    ax.plot(x, a.seances * 0.01, color=ENCRE, lw=1, ls="--", marker="_", label="Attendu (1 % des séances)")
    ax.set_xticks(x, a.index.astype(str), rotation=0, fontsize=8)
    ax.legend(ncol=6, loc="lower left", bbox_to_anchor=(0, 1.0), fontsize=8)
    ax.grid(axis="x", visible=False)
    ax.set_title("Dépassements de la VaR 99 % par année : les échecs se concentrent en 2008, 2015, 2020 et 2022", pad=26)
    return _sauver(fig, d, "03_depassements_par_annee")


def zones_bale(res, d):
    g = res["backtest"]["glissant_250"]
    fig, ax = plt.subplots(figsize=(10, 3.8))
    ax.axhspan(-0.5, 4.5, color=VERT, alpha=0.08, lw=0)
    ax.axhspan(4.5, 9.5, color=ORANGE, alpha=0.10, lw=0)
    ax.axhspan(9.5, 16, color=ROUGE, alpha=0.08, lw=0)
    for m in mv.MODELES:
        ax.plot(g.index, g[m], color=C_MODELE[m], lw=1.6 if m == res["retenu"] else 1, label=COURT[m])
    for y, t in ((2, "zone verte"), (7, "zone orange"), (12, "zone rouge")):
        ax.text(g.index[-1], y, "  " + t, va="center", fontsize=8, color=ENCRE_2)
    ax.set_ylim(-0.5, 16)
    ax.set_ylabel("Dépassements sur 250 séances")
    ax.legend(ncol=5, loc="lower left", bbox_to_anchor=(0, 1.0))
    ax.set_title("Feux tricolores de Bâle : seuls l'EWMA, la Student et la FHS ne passent jamais au rouge", pad=26)
    return _sauver(fig, d, "04_zones_bale")


def comparaison(res, d):
    t = res["backtest"]["tableau"].set_index("modele")
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 3.9), gridspec_kw={"wspace": 0.35})
    y = np.arange(len(t))
    a1.barh(y, t.depassements, color=[C_MODELE[m] for m in t.index])
    a1.axvline(t.attendus.iloc[0], color=ENCRE, ls="--", lw=1)
    a1.text(t.attendus.iloc[0], len(t) - 0.4, f" attendus : {t.attendus.iloc[0]:.0f}".replace(".", ","), fontsize=8, color=ENCRE_2)
    for k, (m, r) in enumerate(t.iterrows()):
        a1.text(r.depassements + 1, k, f"{r.depassements}  (Kupiec p = {r.p_pof:.2f})".replace(".", ","), va="center", fontsize=8)
    a1.set_yticks(y, [COURT[m] for m in t.index])
    a1.invert_yaxis()
    a1.set_xlim(0, t.depassements.max() * 1.6)
    a1.grid(axis="y", visible=False)
    a1.set_title("Nombre de dépassements, 2008 – 2026", fontsize=10.5)
    for m, r in t.iterrows():
        a2.scatter(r.var_moyenne * 100, r.perte_quantile * 1e4, s=90, color=C_MODELE[m], zorder=3)
        a2.annotate(COURT[m], (r.var_moyenne * 100, r.perte_quantile * 1e4), xytext=(7, -3), textcoords="offset points", fontsize=8.5)
    a2.xaxis.set_major_formatter(_fr(2, " %"))
    a2.set_xlabel("VaR moyenne (coût en capital)")
    a2.set_ylabel("Perte quantile moyenne (pb)")
    a2.set_title("Précision contre prudence", fontsize=10.5)
    _titre(fig, "Comparer les modèles : le bon nombre de dépassements, au moindre coût")
    return _sauver(fig, d, "05_comparaison_modeles")


def decomposition(res, d):
    dec = res["decomposition"]
    fig, ax = plt.subplots(figsize=(10, 3.9))
    y = np.arange(len(dec))
    ax.barh(y - 0.2, dec.part_var_param * 100, height=0.38, color=AXE, label="VaR paramétrique (corrélations moyennes)")
    ax.barh(y + 0.2, dec.part_es * 100, height=0.38, color=[C_MANCHE[m] for m in dec.manche], label="ES historique (dans les pires jours)")
    for k, r in dec.iterrows():
        ax.text(max(r.part_es, r.part_var_param, 0) * 100 + 1, k + 0.2, f"{r.part_es * 100:.0f} %".replace(".", ","), va="center", fontsize=8.5)
    ax.set_yticks(y, dec.manche)
    ax.invert_yaxis()
    ax.axvline(0, color=ENCRE_2, lw=0.8)
    ax.xaxis.set_major_formatter(_fr(0, " %"))
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, handles=[
        matplotlib.patches.Patch(color=AXE, label="VaR paramétrique : contribution avec les corrélations moyennes"),
        matplotlib.patches.Patch(color=PALETTE[0], label="ES historique : contribution dans les pires jours (couleur du facteur)")])
    ax.grid(axis="y", visible=False)
    ax.set_title("D'où vient le risque au 28 octobre 2026 : part de chaque facteur", pad=30)
    return _sauver(fig, d, "06_decomposition")


def decomposition_temps(res, d):
    h = res["historique_mensuel"][MANCHES] * 100
    fig, ax = plt.subplots(figsize=(10, 4))
    pos = h.clip(lower=0)
    neg = h.clip(upper=0)
    ax.stackplot(h.index, *[pos[c] for c in MANCHES], colors=[C_MANCHE[c] for c in MANCHES], labels=MANCHES, alpha=0.9, lw=0)
    ax.stackplot(h.index, *[neg[c] for c in MANCHES], colors=[C_MANCHE[c] for c in MANCHES], alpha=0.9, lw=0)
    ax.axhline(0, color=ENCRE_2, lw=0.8)
    ax.yaxis.set_major_formatter(_fr(0, " %"))
    ax.set_ylabel("Part de l'ES 97,5 %")
    ax.legend(ncol=6, loc="lower left", bbox_to_anchor=(0, 1.0), fontsize=8)
    ax.set_title("Dans les pires jours, le change dollar pèse le plus, sauf en 2020 – 2021 où dominent les actions", pad=26)
    return _sauver(fig, d, "07_decomposition_dans_le_temps")


def resistance(res, d):
    s = res["resistance"].copy()
    s = s.sort_values("rendement")
    fig, ax = plt.subplots(figsize=(10, 6.4))
    y = np.arange(len(s))
    gauche_neg = np.zeros(len(s))
    gauche_pos = np.zeros(len(s))
    for mch in MANCHES:
        v = s[f"c_{mch}"].to_numpy() * 100
        base = np.where(v < 0, gauche_neg, gauche_pos)
        ax.barh(y, v, left=base, color=C_MANCHE[mch], height=0.62, label=mch)
        gauche_neg += np.where(v < 0, v, 0)
        gauche_pos += np.where(v >= 0, v, 0)
    ax.scatter(s.rendement * 100, y, marker="D", color=ENCRE, s=22, zorder=4, label="Total")
    for k, (_, r) in enumerate(s.iterrows()):
        txt = f"{r.rendement * 100:+.1f} %  ({-r.perte_eur * FCFA_PAR_EURO / 1e9:+.1f} Md FCFA)".replace(".", ",").replace("-", "−")
        ax.text(max(gauche_pos[k], 0) + 0.3, k, txt, va="center", fontsize=8)
    ax.set_yticks(y, [("◆ " if t == "historique" else "◇ ") + n for n, t in zip(s.scenario, s.type)], fontsize=8)
    ax.axvline(0, color=ENCRE_2, lw=0.8)
    ax.xaxis.set_major_formatter(_fr(0, " %"))
    ax.set_xlim(gauche_neg.min() * 1.1, max(gauche_pos.max(), 0) + 9)
    ax.legend(ncol=4, loc="lower left", bbox_to_anchor=(0, 1.0), fontsize=8)
    ax.grid(axis="y", visible=False)
    ax.set_title("Tests de résistance sur le portefeuille du 28 octobre 2026 (◆ crise rejouée, ◇ scénario hypothétique)", pad=40)
    return _sauver(fig, d, "08_tests_de_resistance")


def sensibilites(res, d):
    s = res["sensibilites"].dropna(subset=["pv01_eur"])
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 3.5), gridspec_kw={"wspace": 0.45})
    y = np.arange(len(s))
    col = [PALETTE[0] if dv == "EUR" else PALETTE[1] for dv in s.devise]
    a1.barh(y, s.pv01_eur * FCFA_PAR_EURO / 1e6, color=col)
    for k, v in enumerate(s.pv01_eur * FCFA_PAR_EURO / 1e6):
        a1.text(v + 0.1, k, f"{v:.1f} M".replace(".", ","), va="center", fontsize=8)
    a1.set_yticks(y, [l.replace("Obligations d'État zone euro", "Zone euro").replace("Bons du Trésor américain", "Trésor US") for l in s.libelle])
    a1.invert_yaxis()
    a1.set_xlabel("Perte pour +1 pb (millions de FCFA)")
    a1.grid(axis="y", visible=False)
    a1.set_title("PV01 par ligne", fontsize=10.5)
    a2.scatter(s.duration, s.convexite, color=col, s=60)
    for _, r in s.iterrows():
        a2.annotate(r.position.upper().replace("ZE", "ZE ").replace("US", "US "), (r.duration, r.convexite),
                    xytext=(6, 6) if r.devise == "EUR" else (6, -11), textcoords="offset points", fontsize=8)
    a2.set_xlabel("Duration modifiée")
    a2.set_ylabel("Convexité")
    a2.set_title("Duration et convexité", fontsize=10.5)
    _titre(fig, "Sensibilités aux taux : bleu, courbe euro ; orange, courbe dollar")
    return _sauver(fig, d, "09_sensibilites")


def attribution(res, d):
    a = res["attribution"][MANCHES] * FCFA_PAR_EURO / 1e9
    fig, ax = plt.subplots(figsize=(10, 4))
    x = np.arange(len(a))
    bas_p = np.zeros(len(a))
    bas_n = np.zeros(len(a))
    for mch in MANCHES:
        v = a[mch].to_numpy()
        ax.bar(x, v, bottom=np.where(v >= 0, bas_p, bas_n), color=C_MANCHE[mch], label=mch, width=0.7)
        bas_p += np.where(v >= 0, v, 0)
        bas_n += np.where(v < 0, v, 0)
    ax.scatter(x, a.sum(axis=1), color=ENCRE, marker="D", s=18, zorder=4, label="Total")
    ax.set_xticks(x, a.index.astype(str), fontsize=8)
    ax.yaxis.set_major_formatter(_fr(0, " Md"))
    ax.set_ylabel("Gain ou perte (milliards de FCFA)")
    ax.legend(ncol=7, loc="lower left", bbox_to_anchor=(0, 1.0), fontsize=8)
    ax.grid(axis="x", visible=False)
    ax.set_title("Ce qui a rapporté et coûté, année par année", pad=26)
    return _sauver(fig, d, "10_attribution")


def horizon_10j(res, d):
    j = res["jour"].set_index("modele")
    mc = res["mc_distribution"] * 100
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 3.7), gridspec_kw={"wspace": 0.3, "width_ratios": [1.2, 1]})
    lo, hi = np.quantile(mc, [0.0005, 0.9995])
    a1.hist(mc.clip(lo, hi), bins=100, range=(lo, hi), color=AXE, edgecolor=FOND, lw=0.2)
    a1.set_xlim(lo, hi)
    v, e = j.loc["mc", "var99_1j"] * 100, j.loc["mc", "es975_1j"] * 100
    a1.axvline(-v, color=PALETTE[0], lw=1.4)
    a1.axvline(-e, color=ROUGE, lw=1.4, ls="--")
    a1.text(-v, a1.get_ylim()[1] * 0.92, f" VaR 99 % : {v:.2f} %".replace(".", ","), color=PALETTE[0], fontsize=8)
    a1.text(-e, a1.get_ylim()[1] * 0.8, f"ES 97,5 % : {e:.2f} % ".replace(".", ","), color=ROUGE, fontsize=8, ha="right")
    a1.xaxis.set_major_formatter(_fr(1, " %"))
    a1.set_title("Monte-Carlo, 20 000 tirages, un jour", fontsize=10.5)
    a1.set_ylabel("Tirages")
    dd = j.dropna(subset=["var99_10j_direct"])
    y = np.arange(len(dd))
    a2.barh(y - 0.2, dd.var99_10j_racine * 100, height=0.38, color=AXE, label="Règle de la racine de 10")
    a2.barh(y + 0.2, dd.var99_10j_direct * 100, height=0.38, color=PALETTE[0], label="Calcul direct à 10 jours")
    a2.set_yticks(y, [COURT[m] for m in dd.index])
    a2.xaxis.set_major_formatter(_fr(1, " %"))
    a2.legend(loc="lower left", bbox_to_anchor=(0, 1.0), fontsize=8, ncol=1)
    a2.grid(axis="y", visible=False)
    a2.set_title("VaR 99 % à 10 jours", fontsize=10.5, pad=34)
    _titre(fig, "Le risque du jour et à dix jours")
    return _sauver(fig, d, "11_monte_carlo_10_jours")


def limite_var(res, d):
    p = res["previsions"]
    r = res["retenu"]
    v = p[f"{r}_var99"] * 100
    fig, ax = plt.subplots(figsize=(10, 3.4))
    ax.plot(v.index, v, color=PALETTE[0], lw=1.1, label=f"VaR 99 % à 1 jour ({COURT[r]})")
    L = LIMITES["var99_1j"]
    ax.axhline(L, color=ROUGE, lw=1.2, label=f"Limite : {L:.2f} %".replace(".", ","))
    ax.axhline(L * 0.8, color=ORANGE, lw=1, ls="--", label="Seuil de vigilance (80 %)")
    ax.fill_between(v.index, v, L, where=v > L, color=ROUGE, alpha=0.4, lw=0, interpolate=True)
    ax.yaxis.set_major_formatter(_fr(1, " %"))
    part = (v > L).mean() * 100
    ax.legend(ncol=3, loc="lower left", bbox_to_anchor=(0, 1.0))
    ax.set_title(f"La limite de VaR aurait été dépassée {part:.1f} % des séances depuis 2008".replace(".", ","), pad=26)
    return _sauver(fig, d, "12_limite_var")


def couverture(res, d):
    c = res["couverture"]
    fig, axes = plt.subplots(1, 3, figsize=(10, 3.3), gridspec_kw={"wspace": 0.45})
    x = c.ratio * 100
    for ax, col, titre, sgn in ((axes[0], "volatilite", "Volatilité annuelle", 1), (axes[1], "baisse_max", "Baisse maximale", -1),
                                (axes[2], "cagr", "Rendement annuel", 1)):
        ax.plot(x, c[col] * 100 * sgn, marker="o", color=PALETTE[0])
        for xx, yy in zip(x, c[col] * 100 * sgn):
            ax.annotate(f"{yy:.1f}".replace(".", ","), (xx, yy), xytext=(0, 6), textcoords="offset points", ha="center", fontsize=7.5)
        ax.set_xticks(x, [f"{v:.0f} %" for v in x])
        ax.yaxis.set_major_formatter(_fr(1, " %"))
        ax.set_title(titre, fontsize=10.5)
        ax.set_xlabel("Part du dollar couverte")
    _titre(fig, "Couvrir le dollar réduit la volatilité, mais aggrave la pire baisse et coûte du rendement")
    return _sauver(fig, d, "13_couverture_dollar")


def tout(res, d: Path) -> list[Path]:
    return [valeur(res, d), var_et_rendements(res, d),
            var_et_rendements(res, d, "2020-01-01", "2020-12-31", "02b_var_2020", "Covid-19 : la VaR historique réagit trop tard, l'EWMA et la FHS en quelques jours"),
            depassements_annuels(res, d), zones_bale(res, d), comparaison(res, d), decomposition(res, d),
            decomposition_temps(res, d), resistance(res, d), sensibilites(res, d), attribution(res, d), horizon_10j(res, d), limite_var(res, d),
            couverture(res, d)]
