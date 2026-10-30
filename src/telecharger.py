"""Télécharge les données de marché (à lancer dans Colab ou sur un poste connecté) : python src/telecharger.py

Le dépôt contient déjà les fichiers figés du 30 octobre 2026 : ce script ne sert qu'à mettre l'étude à jour.
Il produit donnees_risque_marche/ et donnees_risque_marche.zip ; copier ensuite les fichiers dans data/marches/.
"""
import io, time, zipfile, datetime as dt
from pathlib import Path
import pandas as pd, requests

D = Path("donnees_risque_marche"); D.mkdir(exist_ok=True)
H = {"User-Agent": "Mozilla/5.0"}
rapport = []

def get(url, essais=4, delai=120):
    for i in range(essais):
        try:
            r = requests.get(url, headers=H, timeout=delai); r.raise_for_status(); return r
        except Exception as e:
            if i == essais - 1: raise
            time.sleep(5 * (i + 1))

# 1. Trésor américain : courbe des taux quotidienne, toutes échéances, 2005-2026
for an in range(2005, dt.date.today().year + 1):
    url = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/"
           f"{an}/all?type=daily_treasury_yield_curve&field_tdr_date_value={an}&page&_format=csv")
    try:
        d = pd.read_csv(io.StringIO(get(url).text)); d.to_csv(D / f"tresor_{an}.csv", index=False)
        rapport.append(f"OK  tresor_{an}: {len(d)} lignes")
    except Exception as e:
        rapport.append(f"ERR tresor_{an}: {e}")

# 2. BCE : courbe des taux zéro-coupon des États notés AAA de la zone euro (depuis septembre 2004),
#    taux de change de référence euro/dollar, €STR
ECHEANCES = ["3M", "6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "15Y", "20Y", "30Y"]
SERIES_BCE = {f"bce_zc_{e}": f"YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_{e}" for e in ECHEANCES}
SERIES_BCE["bce_eurusd"] = "EXR/D.USD.EUR.SP00.A"
SERIES_BCE["bce_estr"] = "EST/B.EU000A2X2A25.WT"
for nom, cle in SERIES_BCE.items():
    try:
        t = get(f"https://data-api.ecb.europa.eu/service/data/{cle}?format=csvdata&startPeriod=2004-01-01").text
        d = pd.read_csv(io.StringIO(t))[["TIME_PERIOD", "OBS_VALUE"]]
        d.to_csv(D / f"{nom}.csv", index=False)
        rapport.append(f"OK  {nom}: {len(d)} lignes, {d.TIME_PERIOD.min()} au {d.TIME_PERIOD.max()}")
    except Exception as e:
        rapport.append(f"ERR {nom}: {e}")

# 3. Yahoo Finance : indices actions, or, volatilité
import yfinance as yf
TICKERS = ["^STOXX50E", "^GSPC", "GC=F", "^VIX", "EURUSD=X"]
try:
    px = yf.download(TICKERS, start="2004-01-01", auto_adjust=True, progress=False)["Close"]
    px.to_csv(D / "yahoo_cloture.csv")
    debuts = {c: px[c].first_valid_index() for c in px.columns}
    rapport.append(f"OK  yahoo_cloture: {len(px)} lignes, " + ", ".join(f"{c} depuis {d.date()}" for c, d in debuts.items() if d is not None))
except Exception as e:
    rapport.append(f"ERR yahoo_cloture: {e}")

(D / "RAPPORT.txt").write_text(f"Téléchargement du {dt.datetime.now():%Y-%m-%d %H:%M} (UTC)\n" + "\n".join(rapport))
print("\n".join(rapport))
with zipfile.ZipFile("donnees_risque_marche.zip", "w", zipfile.ZIP_DEFLATED) as z:
    for f in sorted(D.iterdir()): z.write(f, f.name)
try:
    from google.colab import files; files.download("donnees_risque_marche.zip")
except ImportError:
    print("Fichier prêt : donnees_risque_marche.zip")
