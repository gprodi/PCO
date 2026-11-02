# Installation (toutes machines)

## Prérequis
- [uv](https://docs.astral.sh/uv/), Git, Docker Desktop (Windows : WSL2 ; GPU NVIDIA : NVIDIA Container Toolkit).
- **Ollama** : Mac M4 → application native (Metal, Docker n'a pas accès au GPU) ; Windows → natif ou profil compose `ai-gpu`.

## Démarrage en 5 commandes
```bash
git clone https://github.com/gprodi/PCO && cd PCO
uv sync --all-packages --group dev --extra data --extra app
uv run llm-gateway doctor            # détecte la machine et choisit les modèles
cp microforge/.env.example microforge/.env
cd microforge/infra && docker compose --profile core up -d --build
```
Puis http://localhost:8501 (preuve de concept), http://localhost:8000/docs et http://localhost:8001/docs (OpenAPI).

## Modèles locaux selon la machine
| Machine | Profil | Commandes |
|---|---|---|
| Mac mini M4 16 Go | `mac-m4-16` | `ollama pull qwen3:8b && ollama pull qwen3-vl:8b && ollama pull bge-m3` |
| PC bureau, GPU 8 Go | `gpu-8gb` | idem + `qwen3:14b` |
| PC école, GPU 6 Go | `gpu-6gb` | `ollama pull qwen3:4b && ollama pull qwen3-vl:4b && ollama pull nomic-embed-text` |

## Tests
```bash
uv run pytest --cov            # couverture >= 80 % exigée
uv run ruff check . && uv run ruff format --check .
```
