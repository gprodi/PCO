# Paramétrage du service d'IA : Ollama + passerelle LiteLLM (C8)

## Environnement d'exécution
| Machine | Ollama | Passerelle |
|---|---|---|
| Mac mini M4 | application native (Metal) | conteneur `litellm` (profil `ai`) |
| PC bureau (GPU 8 Go) | conteneur `ollama` (profil `ai-gpu`, NVIDIA Container Toolkit) ou natif | conteneur `litellm` |
| PC école | natif (modèles 4B) | facultative (`LLM_CHAIN=ollama,gemini`) |

## Dépendances
- Modèles : `ollama pull qwen3:8b qwen3-vl:8b bge-m3` (selon `llm-gateway doctor`).
- Configuration : `microforge/infra/litellm/config.yaml` (alias `mf-text`, `mf-code`, `mf-vision`, `mf-embed`,
  repli Gemini (offre gratuite), délais, tentatives).
- **Sécurité de la chaîne** : LiteLLM uniquement en image Docker, jamais depuis PyPI (versions 1.82.7/1.82.8
  compromises en mars 2026). L'image suit encore le tag `main-stable` : épinglage de la v1.106.6 par empreinte,
  après vérification de sa signature cosign, à faire (veille 2026-45).

## Accès
- Ollama **non exposé** : réseau Docker interne `backend` uniquement.
- LiteLLM : clé maître dans `.env` ; **clés virtuelles par service** avec budget et limite de débit :
```bash
curl -X POST http://localhost:4000/key/generate -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -d '{"key_alias": "api_ia", "models": ["mf-vision","mf-code","mf-text"], "rpm_limit": 60, "max_budget": 5}'
```
- Interface d'administration liée à `127.0.0.1` (Traefik + authentification en préproduction).

## Monitoring
- Métriques Prometheus de LiteLLM (requêtes, latence, tokens, erreurs, replis) + `mf_llm_calls` de l'API IA,
  tableau de bord Grafana « Application » ; sonde Uptime Kuma sur `/health/liveliness` de LiteLLM.

## Test de bon fonctionnement
```bash
uv run llm-gateway doctor
LLM_CHAIN=litellm LITELLM_API_KEY=sk-... uv run llm-gateway ask "Donne le brochage I2C d'un ESP32"
```

## Données impliquées
Prompts (spécifications de projets, sans données personnelles) et photos nettoyées (sans EXIF) ;
rien n'est conservé par Ollama ; LiteLLM journalise les métadonnées (modèle, tokens, durée), pas les contenus.
