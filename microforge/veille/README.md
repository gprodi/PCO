# Kit de veille (C6) — technique & réglementaire

| Fichier | Contenu |
|---|---|
| `plan-de-veille.md` | thématiques, objectifs, planning (≥ 1 h/semaine), outils, diffusion |
| `sources.opml` | flux RSS à importer dans FreshRSS (`docker compose --profile veille up -d`, http://localhost:8080) |
| `grille-fiabilite.md` | grille de notation /7 et évaluation de chaque source |
| `modele-synthese.md` | gabarit accessible d'une synthèse hebdomadaire |
| `journal.md` | journal des sessions (preuve de régularité pour le jury) |
| `syntheses/` | une synthèse par semaine (`AAAA-SS.md`) |
| `veille_weekly.py` | brouillon automatique : FreshRSS -> LLM local -> Markdown (relecture humaine obligatoire) |
| `../src/microforge/veille/` | outil `mf-veille` : OPML → flux RSS/Atom (analyse XML durcie) → articles récents classés par thématique (mots-clés du plan, fiabilité de la source, fraîcheur) → `brouillon.md` + `articles.json` |
| `../../.github/workflows/veille.yml` | chaque lundi 06 h 43 UTC sur un runner GitHub : brouillon en artefact + tableau des flux en échec |

## Utilisation

Brouillon de la semaine (sans IA, extractif) puis, si Ollama tourne, un « En bref » proposé par le modèle local :

```bash
uv run mf-veille --days 7 --out veille-sortie --no-llm
```

```bash
uv run mf-veille --days 7 --out veille-sortie --llm
```

Importer les sources dans FreshRSS (profil compose `veille`, utilisateur à créer au premier lancement) :

```bash
docker compose -f microforge/infra/docker-compose.yml --profile veille exec freshrss ./cli/import-for-user.php --user gael --filename /opml/sources.opml
```

Le brouillon n'est **jamais** publié tel quel : chaque information retenue est vérifiée à la source, notée
avec la grille de fiabilité, puis rédigée dans `syntheses/AAAA-SS.md` (exemple : `syntheses/2026-45.md`).
