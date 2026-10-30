"""Chargement des données de marché et construction des facteurs de risque.

Sources (fichiers figés dans data/marches/, voir SOURCES.md) :
  - Trésor américain : courbe des taux de rendement au pair, quotidienne ;
  - BCE : courbe zéro-coupon des États notés AAA de la zone euro, taux de change de référence euro/dollar ;
  - Yahoo Finance : Euro Stoxx 50, S&P 500, or (contrat à terme le plus proche), VIX.

Calendrier : celui de la courbe de la BCE (jours ouvrés TARGET). Une série américaine absente un jour
ouvré européen (jour férié aux États-Unis) reprend sa dernière valeur : sa variation est nulle ce jour-là.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .parametres import DATE_ARRETE, DEBUT_DONNEES

RACINE = Path(__file__).resolve().parents[1]
DOSSIER = RACINE / "data" / "marches"

ECHEANCES_EUR = {"3M": 0.25, "6M": 0.5, "1Y": 1, "2Y": 2, "3Y": 3, "5Y": 5, "7Y": 7, "10Y": 10, "15Y": 15, "20Y": 20, "30Y": 30}
ECHEANCES_USD = {"3 Mo": 0.25, "6 Mo": 0.5, "1 Yr": 1, "2 Yr": 2, "3 Yr": 3, "5 Yr": 5, "7 Yr": 7, "10 Yr": 10, "20 Yr": 20}
YAHOO = {"^STOXX50E": "sx5e", "^GSPC": "spx", "GC=F": "or", "^VIX": "vix"}


def _serie_bce(chemin: Path) -> pd.Series:
    d = pd.read_csv(chemin)
    s = pd.Series(pd.to_numeric(d.iloc[:, 1], errors="coerce").values, index=pd.to_datetime(d.iloc[:, 0], errors="coerce"))
    return s[s.index.notna()].dropna().sort_index()


def courbe_eur(dossier: Path = DOSSIER) -> pd.DataFrame:
    """Taux zéro-coupon AAA zone euro, en %, colonnes = maturités en années."""
    c = {t: _serie_bce(dossier / f"bce_zc_{e}.csv") for e, t in ECHEANCES_EUR.items() if (dossier / f"bce_zc_{e}.csv").exists()}
    return pd.DataFrame(c).sort_index(axis=1)


def courbe_usd(dossier: Path = DOSSIER) -> pd.DataFrame:
    """Taux de rendement au pair des titres du Trésor, en %, colonnes = maturités en années."""
    morceaux = []
    for f in sorted(dossier.glob("tresor_*.csv")):
        d = pd.read_csv(f)
        d.index = pd.to_datetime(d.pop("Date"), format="%m/%d/%Y")
        morceaux.append(d[[c for c in ECHEANCES_USD if c in d.columns]].rename(columns=ECHEANCES_USD))
    c = pd.concat(morceaux).sort_index()
    c = c[~c.index.duplicated(keep="last")]
    return c.apply(pd.to_numeric, errors="coerce")


def yahoo(dossier: Path = DOSSIER) -> pd.DataFrame:
    d = pd.read_csv(dossier / "yahoo_cloture.csv", index_col=0)
    d.index = pd.to_datetime(d.index.str[:10])
    return d[[c for c in YAHOO if c in d.columns]].rename(columns=YAHOO).apply(pd.to_numeric, errors="coerce")


def charger(dossier: Path = DOSSIER, debut: str = DEBUT_DONNEES, fin: str = DATE_ARRETE) -> dict:
    """Toutes les séries alignées sur le calendrier de la BCE."""
    eur = courbe_eur(dossier).loc[debut:fin]
    cal = eur.dropna(how="all").index
    usd = courbe_usd(dossier).reindex(cal.union(courbe_usd(dossier).index)).ffill(limit=5).reindex(cal)
    usd = usd.interpolate(axis=1, limit_area="inside")      # échéance manquante un jour donné : interpolée
    fx = _serie_bce(dossier / "bce_eurusd.csv").reindex(cal.union(_serie_bce(dossier / "bce_eurusd.csv").index)).ffill(limit=5).reindex(cal)
    px = yahoo(dossier)
    px = px.reindex(cal.union(px.index)).ffill(limit=5).reindex(cal)
    eur = eur.ffill(limit=5)
    debut_commun = max(s.first_valid_index() for s in [eur.iloc[:, 0], usd[2.0], fx, px["sx5e"], px["spx"], px["or"]])
    garde = cal[cal >= debut_commun]
    journal = [f"Calendrier BCE : {len(garde)} séances du {garde[0].date()} au {garde[-1].date()}",
               f"Courbe euro : maturités {list(eur.columns)} ; courbe dollar : {list(usd.columns)}"]
    return {"eur": eur.loc[garde], "usd": usd.loc[garde], "eurusd": fx.loc[garde], "prix": px.loc[garde], "journal": journal}


def interpoler(courbe: pd.DataFrame | np.ndarray, maturites, t):
    """Interpolation linéaire du taux à la maturité t (vectorisée sur les dates)."""
    m = np.asarray(maturites, dtype=float)
    v = np.asarray(courbe, dtype=float)
    if v.ndim == 1:
        return np.interp(t, m, v)
    i = np.clip(np.searchsorted(m, t) - 1, 0, len(m) - 2)
    w = (t - m[i]) / (m[i + 1] - m[i])
    return v[..., i] * (1 - w) + v[..., i + 1] * w


def interpoler_par_ligne(courbe, maturites, t):
    """Taux de chaque ligne (date) à sa propre maturité t[ligne]."""
    m = np.asarray(maturites, dtype=float)
    v = np.asarray(courbe, dtype=float)
    t = np.asarray(t, dtype=float)
    i = np.clip(np.searchsorted(m, t) - 1, 0, len(m) - 2)
    w = (t - m[i]) / (m[i + 1] - m[i])
    r = np.arange(len(v))
    return v[r, i] * (1 - w) + v[r, i + 1] * w
