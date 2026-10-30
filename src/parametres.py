"""Paramètres du portefeuille et des modèles. Tout ce qui est fixé à l'avance est ici, rien n'est choisi après coup."""
from __future__ import annotations

from dataclasses import dataclass

FCFA_PAR_EURO = 655.957
VALEUR_FCFA = 100e9                        # 100 milliards de FCFA
VALEUR_EUR = VALEUR_FCFA / FCFA_PAR_EURO   # 152,4 millions d'euros
DEBUT_DONNEES = "2005-01-01"
DATE_ARRETE = "2026-10-28"


@dataclass(frozen=True)
class Position:
    code: str
    libelle: str
    classe: str        # "monetaire", "obligation", "action", "or"
    devise: str        # "EUR" ou "USD"
    poids: float
    maturite: float | None = None       # années, pour les obligations
    frequence: int = 1                  # coupons par an : 1 en zone euro, 2 aux États-Unis
    facteur: str | None = None          # série de prix pour les actions et l'or


# Allocation stratégique d'une trésorerie institutionnelle prudente, fixée a priori et rééquilibrée chaque jour.
# Elle reprend la structure type des portefeuilles de réserves : surtout des titres d'État de haute qualité,
# une poche en dollars, une petite poche d'actions et de l'or (FMI, Revised Guidelines for Foreign Exchange
# Reserve Management, 2013 ; enquêtes annuelles sur les réserves des banques centrales).
POSITIONS = [
    Position("liq", "Liquidités en euros", "monetaire", "EUR", 0.10),
    Position("ze2", "Obligations d'État zone euro 2 ans", "obligation", "EUR", 0.20, 2, 1),
    Position("ze5", "Obligations d'État zone euro 5 ans", "obligation", "EUR", 0.15, 5, 1),
    Position("ze10", "Obligations d'État zone euro 10 ans", "obligation", "EUR", 0.10, 10, 1),
    Position("us2", "Bons du Trésor américain 2 ans", "obligation", "USD", 0.10, 2, 2),
    Position("us5", "Bons du Trésor américain 5 ans", "obligation", "USD", 0.10, 5, 2),
    Position("us10", "Bons du Trésor américain 10 ans", "obligation", "USD", 0.05, 10, 2),
    Position("actze", "Actions zone euro (Euro Stoxx 50)", "action", "EUR", 0.075, facteur="sx5e"),
    Position("actus", "Actions américaines (S&P 500)", "action", "USD", 0.075, facteur="spx"),
    Position("or", "Or", "or", "USD", 0.05, facteur="or"),
]
assert abs(sum(p.poids for p in POSITIONS) - 1) < 1e-12

# Groupes de facteurs de risque pour la décomposition
GROUPES = {"liq": "Taux euro", "ze2": "Taux euro", "ze5": "Taux euro", "ze10": "Taux euro",
           "us2": "Taux dollar", "us5": "Taux dollar", "us10": "Taux dollar",
           "actze": "Actions", "actus": "Actions", "or": "Or"}

# Modèles de VaR
NIVEAU_VAR = 0.99
NIVEAU_ES = 0.975
FENETRE_HS = 500          # séances, simulation historique (deux ans)
FENETRE_PARAM = 250       # séances, VaR paramétrique normale et Student
LAMBDA_EWMA = 0.94        # RiskMetrics (J.P. Morgan, 1996)
FENETRE_GARCH = 1000      # séances, estimation du GARCH(1,1)
REESTIMATION_GARCH = 21   # séances entre deux estimations
N_MONTE_CARLO = 20000
GRAINE = 20261030

# Dispositif de limites (en % de la valeur du portefeuille)
LIMITES = {
    "var99_1j": 1.00,                 # VaR à 99 % sur un jour : environ le 95e centile de la VaR 2008-2026
    "es975_1j": 1.10,                 # Expected Shortfall à 97,5 % sur un jour
    "pv01_eur": 0.025,                # perte pour +1 pb sur toute la courbe euro
    "pv01_usd": 0.015,                # perte pour +1 pb sur toute la courbe dollar
    "change_usd": 50.0,               # exposition brute au dollar
    "perte_mois": 2.0,                # perte cumulée depuis le début du mois calendaire
}
SEUIL_VIGILANCE = 0.80                # orange à partir de 80 % de la limite
