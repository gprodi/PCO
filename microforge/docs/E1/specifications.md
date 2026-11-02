# Spécifications techniques de la collecte (C1)

## Technologies et outils
Python 3.12+, uv, httpx + tenacity, BeautifulSoup/lxml, Playwright (si JavaScript), Polars, PySpark,
sqlite3, google-cloud-bigquery (option), Prefect 3, loguru, pytest + respx. Code : `microforge/src/microforge/data_pipeline/`.

## Sources et contraintes identifiées
| Type (C1) | Source | Accès | Contraintes | Données utiles |
|---|---|---|---|---|
| Service web REST | DigiKey Product Information v4 | OAuth2 client credentials (compte dev gratuit) | quotas min/jour, locale FR/EUR, CGU | MPN, fabricant, paramètres (tension, interface), prix, stock, datasheet |
| Service web REST | Mouser Search API | clé d'API | quota non publié → 1 req/s, prix en texte localisé | prix EUR, stock |
| Service web REST | GitHub REST | jeton lecture seule | 5 000 req/h | étoiles, activité, licence des bibliothèques |
| Service web REST | Frankfurter (BCE) | libre | 1 appel/jour suffit | taux de change → EUR |
| Fichier | `library_index.json` Arduino | téléchargement HTTPS | volumineux, toutes versions | bibliothèques, `#include`, architectures |
| Fichier | pièces Fritzing `.fzp` (XML) | `git clone` | licence CC-BY-SA (citer) | brochages de modules |
| Scraping | boutique française (config `shops.yaml`) | HTML public | CGU + `robots.txt`, délai 3 s, User-Agent identifié | prix TTC, disponibilité |
| Base de données | jlcparts `cache.sqlite3` (LCSC) | fichier SQLite ~11 Go (lecture seule) | volumétrie, instantané daté | catalogue, stock, grilles de prix |
| Big data | Spark SQL sur le dump LCSC (Parquet) | local `local[*]` | mémoire selon le profil (4–16 Go) | statistiques par catégorie |
| Big data (option) | BigQuery `github_repos.sample_contents` | projet GCP | **dry-run obligatoire**, plafond 60 Go | co-occurrences d'`#include` |

## Structure de chaque script (critère C1)
`Extractor.run()` : 1. point de lancement → 2. `setup()` initialisation → 3. `extract()` traitement →
4. gestion des erreurs (exception typée, statut `failed`, journalisée) → 5. `save()` :
`data/raw/<source>/<date>/records.jsonl` + `manifest.json` (lignes, durée, SHA-256, paramètres sans secret).

## Exécution
```bash
uv run mf-pipeline extract fx
uv run mf-pipeline extract digikey --keywords "DHT22,BME280"
uv run mf-pipeline extract jlcparts --path data/external/cache.sqlite3
uv run mf-pipeline spark --sqlite data/external/cache.sqlite3 --driver-memory 16g
uv run mf-pipeline run          # flow Prefect complet
```
