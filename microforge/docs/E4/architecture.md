# Cadre technique (C15)

## Architecture (micro-services, n-tiers)
```mermaid
flowchart LR
  subgraph Client
    PWA[PWA React] & ST[Streamlit POC]
  end
  subgraph Services
    DATA[api_data FastAPI] --- PG[(PostgreSQL + pgvector)]
    IA[api_ia FastAPI] --- CORE[cœur déterministe]
    IA --- GW[llm_gateway] --- LLM[LiteLLM → Ollama / Gemini / Claude]
    IA --- MODEL[(YOLO @production)]
  end
  subgraph MLOps
    MLF[MLflow] --- S3[(S3 SeaweedFS)]
    PIPE[Pipeline E1 Prefect] --> PG
  end
  subgraph Observabilité
    PROM[Prometheus] --> GRAF[Grafana] ; LOKI[Loki + Alloy] --> GRAF ; KUMA[Uptime Kuma]
  end
  PWA & ST -->|HTTPS + JWT| DATA & IA
```

## Diagramme de flux de données (critère C15)
```mermaid
flowchart LR
  U((Utilisateur)) -- photo --> IA -- image nettoyée --> V[Vision YOLO+VLM]
  V -- composants --> U
  U -- inventaire validé --> DATA --> PG
  U -- retours --> DATA --> PG -- taux de corrections --> PROM
  SRC[(Sources E1 : API, fichiers, scraping, BDD, big data)] --> PIPE --> PG
  IA -- spec --> CORE -- câblage, code, BOM --> U
  logs[(Journaux JSON)] --> LOKI
```

## Choix techniques
| Besoin | Choix | Alternatives écartées |
|---|---|---|
| Langage back | Python 3.12 + FastAPI (vu en formation, typage Pydantic, OpenAPI) | Node.js |
| Front | Streamlit (POC) puis React + Vite PWA (caméra, hors ligne, WebSerial) | Flutter (2 bases de code) |
| Base | PostgreSQL + pgvector | MongoDB (données relationnelles) |
| IA | Ollama local + LiteLLM (cf. E2) | API cloud seules |
| Hébergement préprod | VPS chez un hébergeur européen éco-engagé (Scaleway / OVHcloud / Infomaniak, comparés dans le benchmark) | hyperscalers US |

## Preuve de concept
Accessible en préproduction (compose `core` derrière Traefik + Let's Encrypt). Conclusion **go** :
le parcours photo → projet fonctionne de bout en bout (captures et tests E2E Playwright joints).
