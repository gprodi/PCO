# Intégration continue (C18)

Outil : **GitHub Actions** (dépôt sur GitHub, gratuit, vu en formation). Fichier `.github/workflows/ci.yml`.

| Job | Déclencheur | Étapes |
|---|---|---|
| `python` (matrice 3.12 / 3.13) | push sur `main`, `claude/**`, `feature/**`, toute PR, manuel | installation uv (cache) → `ruff check` + `ruff format --check` → `pytest --cov` (**porte 80 %**) → rapport de couverture |
| `firmware` | idem | génération de 5 projets de démonstration → `arduino-cli compile` (Uno) |
| `secrets` | idem | gitleaks sur tout l'historique |

Toutes les actions sont **épinglées par SHA** (veille sécurité 2026). Dépendances suivies par Dependabot.

Utilisation : la CI se lance seule à chaque push ; relance manuelle via *Actions > ci > Run workflow* ;
une PR ne peut être fusionnée que si la CI est verte (protection de branche).
