"""Rapport de risque quotidien d'une page (HTML, converti en PDF par Chromium si Playwright est installé)."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from .analyses import MANCHES
from .backtest import zone_bale
from .modeles_var import LIBELLES, MODELES
from .parametres import FCFA_PAR_EURO, VALEUR_FCFA

MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]


def _fr(x, d=2, signe=False):
    s = f"{x:+,.{d}f}" if signe else f"{x:,.{d}f}"
    return s.replace(",", " ").replace(".", ",").replace("-", "−")


def _date(d):
    return f"{d.day} {MOIS[d.month - 1]} {d.year}"


def html(res) -> str:
    d = res["date"]
    j = res["jour"].set_index("modele")
    r = res["retenu"]
    var = j.loc[r, "var99_1j"]
    es = j.loc[r, "es975_1j"]
    v10 = j.loc["hs", "var99_10j_direct"]
    s = res["resistance"]
    pire = s.loc[s.rendement.idxmin()]
    lim = res["limites"]
    g = res["backtest"]["glissant_250"].iloc[-1]
    dec = res["decomposition"]
    couleurs = {"vert": "#1e8449", "orange": "#b9770e", "rouge": "#c0392b"}
    fonds = {"vert": "#e3f4e8", "orange": "#fcefd9", "rouge": "#f9e0dc"}
    pal = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]

    lignes_lim = "".join(
        f"<tr><td>{x.libelle}</td><td class='n'>{_fr(x.valeur, 3 if x.valeur < 1 else 2)}</td><td class='n'>{_fr(x.limite, 3 if x.limite < 1 else 2)}</td>"
        f"<td><div class='jauge'><i style='width:{min(x.utilisation, 1) * 100:.0f}%;background:{couleurs[x.statut]}'></i></div></td>"
        f"<td class='n'>{x.utilisation * 100:.0f} %</td><td><span class='pastille' style='background:{fonds[x.statut]};color:{couleurs[x.statut]}'>{x.statut}</span></td></tr>"
        for x in lim.itertuples())
    lignes_mod = "".join(
        f"<tr{' class=ref' if m == r else ''}><td>{LIBELLES[m]}{' (référence)' if m == r else ''}</td>"
        f"<td class='n'>{_fr(j.loc[m, 'var99_1j'] * 100, 2)} %</td><td class='n'>{_fr(j.loc[m, 'var99_1j'] * VALEUR_FCFA / 1e6, 0)}</td>"
        f"<td class='n'>{_fr(j.loc[m, 'es975_1j'] * 100, 2)} %</td>"
        + (f"<td class='n'>{int(g[m])}</td><td><span class='pastille' style='background:{fonds[zone_bale(int(g[m]))]};color:{couleurs[zone_bale(int(g[m]))]}'>{zone_bale(int(g[m]))}</span></td>"
           if m in MODELES else "<td class='n'>–</td><td>–</td>") + "</tr>"
        for m in list(MODELES) + ["mc"])
    top = s.sort_values("rendement").head(6)
    lignes_st = "".join(f"<tr><td>{x.scenario}</td><td class='n'>{_fr(x.rendement * 100, 1, True)} %</td>"
                        f"<td class='n'>{_fr(-x.perte_eur * FCFA_PAR_EURO / 1e9, 1, True)}</td></tr>" for x in top.itertuples())
    mx = max(abs(dec.part_es).max(), 0.01)
    barres = "".join(f"<div class='bar'><span>{x.manche}</span><div class='piste'><i style='width:{max(x.part_es, 0) / mx * 100:.0f}%;background:{pal[k]}'></i></div>"
                     f"<b>{x.part_es * 100:.0f} %</b></div>" for k, x in enumerate(dec.itertuples()))
    n_rouge = (lim.statut == "rouge").sum()
    n_orange = (lim.statut == "orange").sum()
    synthese = ("Toutes les limites sont respectées." if n_rouge == 0 and n_orange == 0 else
                f"{n_rouge} limite(s) dépassée(s), {n_orange} en vigilance.")
    fx = dec.set_index("manche").loc["Change dollar", "part_es"]
    k = pire.multiple_inverse
    inverse = (f"{_fr(k * 100, 0)} % de son ampleur suffiraient à faire perdre 5 % de la valeur." if k < 1 else
               f"il faudrait l'amplifier {_fr(k, 2)} fois pour perdre 5 % de la valeur.")
    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>Rapport de risque du {_date(d)}</title>
<style>
@page {{ size: A4; margin: 12mm 12mm 10mm; }}
* {{ box-sizing: border-box; }}
body {{ font: 9.4pt/1.35 "DejaVu Sans", Arial, sans-serif; color: #14213d; margin: 0; }}
h1 {{ font-size: 15pt; margin: 0; }} h2 {{ font-size: 10pt; margin: 0 0 4px; color: #13213a; text-transform: uppercase; letter-spacing: .04em; }}
.tete {{ display: flex; justify-content: space-between; align-items: end; border-bottom: 2px solid #13213a; padding-bottom: 6px; margin-bottom: 8px; }}
.tete p {{ margin: 2px 0 0; color: #4a5568; }}
.kpi {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-bottom: 8px; }}
.kpi div {{ border: 1px solid #d8dee8; border-top: 3px solid #2a78d6; padding: 6px 8px; }}
.kpi b {{ display: block; font-size: 14pt; }} .kpi span {{ color: #4a5568; font-size: 8pt; }}
.grille {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
section {{ margin-bottom: 8px; }}
table {{ border-collapse: collapse; width: 100%; font-size: 8.4pt; }}
th {{ text-align: left; color: #4a5568; font-weight: 600; border-bottom: 1px solid #b9c1cc; padding: 3px 4px; }}
td {{ border-bottom: 1px solid #e5e9ef; padding: 3px 4px; }} td.n {{ text-align: right; white-space: nowrap; }}
tr.ref td {{ background: #eef4fc; font-weight: 600; }}
.pastille {{ padding: 1px 6px; border-radius: 8px; font-size: 7.6pt; font-weight: 600; }}
.jauge {{ width: 70px; height: 7px; background: #eef1f5; }} .jauge i {{ display: block; height: 7px; }}
.bar {{ display: grid; grid-template-columns: 120px 1fr 36px; gap: 6px; align-items: center; margin: 2px 0; font-size: 8.4pt; }}
.piste {{ background: #eef1f5; height: 9px; }} .piste i {{ display: block; height: 9px; }} .bar b {{ text-align: right; }}
.lecture {{ background: #f3f6fa; padding: 6px 8px; border-left: 3px solid #13213a; font-size: 8.6pt; }}
.lecture p {{ margin: 2px 0; }}
.pied {{ color: #6a7383; font-size: 7.4pt; margin-top: 4px; }}
</style></head><body>
<div class="tete"><div><h1>Rapport de risque de marché</h1><p>Trésorerie de 100 milliards de FCFA · séance du {_date(d)}</p></div>
<div style="text-align:right"><p>Modèle de référence : <b>{LIBELLES[r]}</b></p><p>{synthese}</p></div></div>
<div class="kpi">
<div><b>{_fr(var * VALEUR_FCFA / 1e6, 0)} M FCFA</b><span>VaR 99 % à 1 jour ({_fr(var * 100, 2)} %)</span></div>
<div><b>{_fr(es * VALEUR_FCFA / 1e6, 0)} M FCFA</b><span>Expected Shortfall 97,5 % à 1 jour ({_fr(es * 100, 2)} %)</span></div>
<div><b>{_fr(v10 * VALEUR_FCFA / 1e9, 2)} Md FCFA</b><span>VaR 99 % à 10 jours, historique directe ({_fr(v10 * 100, 2)} %)</span></div>
<div style="border-top-color:#c0392b"><b>{_fr(-pire.perte_eur * FCFA_PAR_EURO / 1e9, 1, True)} Md FCFA</b><span>Pire test de résistance : {pire.scenario.split(' :')[0]}</span></div>
</div>
<section><h2>Limites</h2><table><tr><th>Indicateur</th><th>Valeur</th><th>Limite</th><th></th><th>Utilisation</th><th>Statut</th></tr>{lignes_lim}</table></section>
<div class="grille">
<section><h2>VaR des six modèles</h2><table><tr><th>Modèle</th><th>VaR 99 %</th><th>M FCFA</th><th>ES 97,5 %</th><th>Dép. 250 j</th><th>Bâle</th></tr>{lignes_mod}</table></section>
<section><h2>D'où vient le risque (part de l'ES)</h2>{barres}
<p class="pied">Contribution de chaque facteur aux pertes des 2,5 % pires scénarios historiques (500 séances).</p></section>
</div>
<div class="grille">
<section><h2>Six pires tests de résistance</h2><table><tr><th>Scénario</th><th>Effet</th><th>Md FCFA</th></tr>{lignes_st}</table></section>
<section><h2>Lecture</h2><div class="lecture">
<p>La VaR de référence utilise {lim.set_index('indicateur').loc['var99_1j', 'utilisation'] * 100:.0f} % de sa limite. Le modèle de référence a connu {int(g[r])} dépassement(s) sur les 250 dernières séances : zone {zone_bale(int(g[r]))}.</p>
<p>Le change dollar explique {fx * 100:.0f} % de l'ES : l'exposition non couverte au dollar ({lim.set_index('indicateur').loc['change_usd', 'valeur']:.1f} % du portefeuille) est le premier risque des mauvais jours.</p>
<p>Le scénario le plus coûteux ferait perdre {_fr(-pire.rendement * 100, 1)} % ; {inverse}</p>
</div></section></div>
<p class="pied">Elisée Boco · données : Trésor américain, BCE, Yahoo Finance · VaR et ES en pertes positives · portefeuille rééquilibré chaque jour · code : github.com/Elisee-Boco/market-risk-dashboard</p>
</body></html>"""


def produire(res, dossier: Path) -> list[Path]:
    dossier.mkdir(parents=True, exist_ok=True)
    h = dossier / "rapport_quotidien.html"
    h.write_text(html(res), encoding="utf-8")
    sorties = [h]
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page()
            page.goto(h.resolve().as_uri())
            pdf = dossier / f"Rapport_risque_{res['date']:%Y-%m-%d}.pdf"
            page.pdf(path=str(pdf), format="A4", print_background=True, prefer_css_page_size=True)
            b.close()
            sorties.append(pdf)
    except Exception as e:                      # Playwright absent (Colab) : le rapport HTML suffit
        print("PDF non produit :", e)
    return sorties
