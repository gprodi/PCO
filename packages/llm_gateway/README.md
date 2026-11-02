# llm-gateway

Client IA commun à **MicroForge** et **Révisions DevIA**.

- **Local d'abord** : Ollama (API compatible OpenAI `/v1`).
- **Secours** : Gemini (offre gratuite, endpoint compatible OpenAI), puis Claude (SDK officiel `anthropic`, payant à l'usage).
- **Ou** une passerelle **LiteLLM** (clés virtuelles, quotas, fallbacks, métriques) : `LLM_CHAIN=litellm`.
- **Profils matériel** détectés automatiquement (`llm-gateway doctor`) : Mac M4 16 Go, GPU 8 Go, GPU 6 Go, CPU.
- **FakeProvider** déterministe pour les tests et les démos hors ligne (`LLM_CHAIN=fake`).

```python
from llm_gateway import Gateway
from pydantic import BaseModel


class Composant(BaseModel):
    reference: str
    categorie: str


gw = Gateway.from_env()
print(gw.chat("Explique le rôle d'une résistance de pull-up", role="text"))
c = gw.structured("Identifie ce composant", schema=Composant, images=[photo_bytes], role="vision")
vecs = gw.embed(["texte 1", "texte 2"])
```

## Variables d'environnement

| Variable | Défaut | Rôle |
|---|---|---|
| `LLM_CHAIN` | `ollama,gemini,anthropic` | ordre de la chaîne de secours (`fake`, `litellm` possibles) |
| `LLM_PROFILE` | auto | forcer un profil (`mac-m4-16`, `gpu-8gb`, `gpu-6gb`, `cpu`) |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | dans Docker : `http://host.docker.internal:11434` |
| `GEMINI_API_KEY` | — | active Gemini |
| `ANTHROPIC_API_KEY` | — | active Claude (installer l'extra `anthropic`) |
| `LITELLM_BASE_URL` / `LITELLM_API_KEY` | — | passerelle LiteLLM |
| `LLM_TIMEOUT_S` | `120` | délai par requête |
