# Données de marché : sources, contenu et empreintes

Fichiers téléchargés le 30 octobre 2026 avec `src/telecharger.py`, exécuté dans Google Colab.
L'étude s'arrête à la séance du **28 octobre 2026** (`DATE_ARRETE` dans `src/parametres.py`).

## Sources

| Fichiers | Source | Contenu utilisé |
|---|---|---|
| `tresor_2005.csv` … `tresor_2026.csv` | Département du Trésor américain, courbe des taux quotidienne : https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_yield_curve | Taux au pair de 3 mois à 20 ans (%), coupon semestriel |
| `bce_zc_3M.csv` … `bce_zc_30Y.csv` | BCE, courbe zéro-coupon des États de la zone euro notés AAA (modèle de Svensson, composition continue), série YC : https://data.ecb.europa.eu/data/datasets/YC | 11 maturités de 3 mois à 30 ans (%) |
| `bce_eurusd.csv` | BCE, taux de change de référence euro/dollar (fixé vers 14 h 15, heure de Francfort), série EXR.D.USD.EUR.SP00.A : https://data.ecb.europa.eu/data/datasets/EXR | Dollars pour un euro |
| `bce_estr.csv` | BCE, €STR, série EST.B.EU000A2X2A25.WT | Contrôle uniquement (depuis octobre 2019) |
| `yahoo_cloture.csv` | Yahoo Finance via `yfinance` | Euro Stoxx 50 (^STOXX50E), S&P 500 (^GSPC), or (GC=F, contrat à terme le plus proche), VIX ; EURUSD=X pour contrôle |

## Ce que l'on sait des données, et leurs limites

- **Début de l'échantillon : 30 mars 2007.** C'est la première cotation de l'Euro Stoxx 50 chez Yahoo. Les autres séries commencent plus tôt (courbe de la BCE : septembre 2004 ; Trésor : 2005). Avec une fenêtre minimale de 250 séances, la première prévision de VaR date du 26 mars 2008 : la crise de 2008 est dans le backtest.
- **Indices de prix, sans dividendes.** Le rendement des actions est sous-estimé d'environ 2 à 3 points par an ; le risque quotidien ne l'est pas.
- **Heures de clôture différentes.** La courbe de la BCE et le change de référence sont fixés à Francfort, les taux américains, le S&P 500 et l'or à New York. Une partie des mouvements américains de l'après-midi apparaît donc dans le change du lendemain. Ce décalage crée un peu d'autocorrélation dans les rendements quotidiens, discutée dans la note.
- **Jours fériés.** Le calendrier est celui de la BCE ; une série absente un jour ouvré européen reprend sa dernière valeur.
- **Le VIX européen (^V2TX)** n'existe plus chez Yahoo ; il était facultatif et n'est pas utilisé.

## Empreintes SHA-256

Pour vérifier que les fichiers n'ont pas changé : `sha256sum data/marches/*.csv`.

| Fichier | Taille | SHA-256 (16 premiers caractères) |
|---|---|---|
| `bce_estr.csv` | 31 Ko | `de741030bac598af…` |
| `bce_eurusd.csv` | 103 Ko | `d41125dbd087c686…` |
| `bce_zc_10Y.csv` | 159 Ko | `116da34c278f4e99…` |
| `bce_zc_15Y.csv` | 159 Ko | `a6da4866e77b8bcc…` |
| `bce_zc_1Y.csv` | 161 Ko | `3d3bb2bb60d48430…` |
| `bce_zc_20Y.csv` | 158 Ko | `9285209d0bb86c64…` |
| `bce_zc_2Y.csv` | 161 Ko | `d8d41bfdc5e061da…` |
| `bce_zc_30Y.csv` | 158 Ko | `d7448d05921716e4…` |
| `bce_zc_3M.csv` | 161 Ko | `f22f33311edb2b2a…` |
| `bce_zc_3Y.csv` | 161 Ko | `6f59591dcd635f2a…` |
| `bce_zc_5Y.csv` | 161 Ko | `bf10366d0a6812ae…` |
| `bce_zc_6M.csv` | 161 Ko | `4f8fa4ee857c0a6f…` |
| `bce_zc_7Y.csv` | 160 Ko | `fdfa1eaeed99f4aa…` |
| `tresor_2005.csv` | 15 Ko | `9c9580c056d7d2a2…` |
| `tresor_2006.csv` | 16 Ko | `5f14ea7e492140ff…` |
| `tresor_2007.csv` | 16 Ko | `e0d33cec21769290…` |
| `tresor_2008.csv` | 16 Ko | `a7e24af1f114fa4d…` |
| `tresor_2009.csv` | 16 Ko | `42b9956b3be88469…` |
| `tresor_2010.csv` | 16 Ko | `7480fbbb2b7bf83c…` |
| `tresor_2011.csv` | 16 Ko | `6b081e269e6eb38d…` |
| `tresor_2012.csv` | 16 Ko | `74702beba6948ad3…` |
| `tresor_2013.csv` | 16 Ko | `c2731a4f3ab00ef5…` |
| `tresor_2014.csv` | 16 Ko | `176bb5d9f59afcf9…` |
| `tresor_2015.csv` | 16 Ko | `1c4b65ed632f4b4a…` |
| `tresor_2016.csv` | 16 Ko | `0662562f4c2ed50d…` |
| `tresor_2017.csv` | 16 Ko | `57bdd42e18924ed1…` |
| `tresor_2018.csv` | 16 Ko | `f5a9ae05d985c407…` |
| `tresor_2019.csv` | 17 Ko | `6fef9962940f730c…` |
| `tresor_2020.csv` | 17 Ko | `2eadb124bacc043a…` |
| `tresor_2021.csv` | 17 Ko | `fadff505a8b54e7b…` |
| `tresor_2022.csv` | 17 Ko | `e14791ac0d75e33a…` |
| `tresor_2023.csv` | 18 Ko | `de6e0ffc0f2991a5…` |
| `tresor_2024.csv` | 18 Ko | `82df11f5bea7f08e…` |
| `tresor_2025.csv` | 19 Ko | `5f1521cca357ad78…` |
| `tresor_2026.csv` | 16 Ko | `f26f91672ec1f6e6…` |
| `yahoo_cloture.csv` | 546 Ko | `918019cadf223d40…` |
