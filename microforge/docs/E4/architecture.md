# Cadre technique (C15)

## C4, niveau 1 : contexte
Qui utilise MicroForge et avec quels systèmes il échange. Seuls les échanges réellement codés figurent.

```mermaid
flowchart LR
  maker(("Maker<br/>[personne]<br/>débutant ou confirmé,<br/>avec un tiroir de composants"))
  mf["MicroForge<br/>[système]<br/>stock, idées de projets, câblage,<br/>code, simulation, guide de soudure"]
  wokwi["Wokwi<br/>[externe]<br/>simulation en ligne"]
  fourn["Fournisseurs et catalogues<br/>[externes]<br/>LCSC/jlcparts, DigiKey, Mouser,<br/>index des bibliothèques Arduino"]
  gemini["Gemini, offre gratuite<br/>[externe, facultatif]<br/>secours du modèle local"]
  gh["GitHub<br/>[externe]<br/>Actions (CI, collecte, entraînement),<br/>GHCR (images)"]
  ds["Jeux de photos publics<br/>[externes]<br/>Mendeley, Roboflow Universe"]
  maker -- "photo du stock, choix de projet" --> mf
  mf -- "câblage, code, nomenclature" --> maker
  mf -- "diagram.json exporté (copier-coller)" --> wokwi
  fourn -- "composants, prix, stock (collecte E1)" --> mf
  mf -. "si Ollama est indisponible" .-> gemini
  gh -- "images Docker, modèle entraîné" --> mf
  ds -- "photos annotées sous licence CC BY" --> gh
```

## C4, niveau 2 : conteneurs
Services du fichier `infra/docker-compose.yml`, regroupés par profil de lancement (`--profile`).

```mermaid
flowchart TB
  maker(("Maker"))
  traefik["Traefik<br/>[reverse proxy, TLS]<br/>à configurer"]:::cible
  pwa["PWA React + Vite<br/>à construire"]:::cible
  subgraph core["profil core"]
    st["Application<br/>[Streamlit, Python]<br/>:8501"]
    data["api_data<br/>[FastAPI]<br/>:8000 — comptes, stock,<br/>catalogue, projets"]
    ia["api_ia<br/>[FastAPI]<br/>:8001 — vision, génération,<br/>copilote"]
    pg[("PostgreSQL 17 + pgvector<br/>données, passages du copilote")]
  end
  subgraph ai["profils ai / ai-gpu"]
    litellm["LiteLLM<br/>[passerelle LLM]<br/>:4000, local uniquement"]
    ollama["Ollama<br/>[modèles locaux]"]
  end
  subgraph mlops["profil mlops"]
    mlflow["MLflow<br/>:5000 — suivi, registre<br/>(@staging, @production)"]
    s3[("SeaweedFS<br/>[S3] :8333 — artefacts")]
  end
  subgraph obs["profil monitoring"]
    prom["Prometheus"] --> graf["Grafana :3000"]
    loki["Loki + Alloy"] --> graf
    kuma["Uptime Kuma :3001"]
  end
  pipe["data_pipeline<br/>[Prefect, CLI mf-pipeline]<br/>collecte E1"]
  maker -- HTTPS --> traefik
  traefik -.-> st
  traefik -.-> pwa
  pwa -. "JSON + JWT" .-> data
  pwa -. "JSON + JWT" .-> ia
  st -- "JSON + JWT" --> data
  st -- "JSON + JWT" --> ia
  data --> pg
  ia -- "clé publique des jetons" --> data
  ia -- "llm_gateway" --> litellm --> ollama
  ia -- "modèle @production" --> mlflow --> s3
  pipe --> pg
  prom -. "métriques /metrics" .-> data
  prom -. "métriques /metrics" .-> ia
  kuma -. "/health" .-> data
  classDef cible stroke-dasharray: 5 4
```
Les éléments en pointillés sont la cible, pas encore en place (voir « Cible et état d'avancement »).

Le profil `veille` ajoute FreshRSS (agrégation des flux de veille, E2).

## Vue d'ensemble (micro-services, n-tiers)
```mermaid
flowchart LR
  subgraph Client
    ST[Streamlit, preuve de concept] & PWA[PWA React, à construire]
  end
  subgraph Services
    DATA[api_data FastAPI] --- PG[(PostgreSQL + pgvector)]
    IA[api_ia FastAPI] --- CORE[cœur déterministe]
    IA --- GW[llm_gateway] --- LLM[LiteLLM → Ollama / Gemini gratuit]
    IA --- MODEL[(YOLO @production)]
  end
  subgraph MLOps
    MLF[MLflow] --- S3[(S3 SeaweedFS)]
    PIPE[Pipeline E1 Prefect] --> PG
  end
  subgraph Observabilité
    PROM[Prometheus] --> GRAF[Grafana] ; LOKI[Loki + Alloy] --> GRAF ; KUMA[Uptime Kuma]
  end
  ST & PWA -->|HTTPS + JWT via Traefik| DATA & IA
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
| Front | Streamlit (preuve de concept, en place), puis PWA React + Vite (à construire : caméra, hors ligne, WebSerial) | Flutter (2 bases de code) |
| Base | PostgreSQL + pgvector | MongoDB (données relationnelles) |
| IA | Ollama local + LiteLLM (cf. E2) | API cloud seules |
| Hébergement préprod | VPS chez un hébergeur européen éco-engagé (Scaleway / OVHcloud / Infomaniak, comparés dans le benchmark) | hyperscalers US |

## Cible et état d'avancement
| Élément | Cible | État au 04/11/2026 |
|---|---|---|
| Application | Streamlit (preuve de concept) puis PWA React + Vite | Streamlit en place ; PWA à construire |
| Accès | Traefik en reverse proxy, TLS Let's Encrypt, redirection HTTPS | à configurer (profil compose dédié) |
| Préproduction | VPS chez un hébergeur européen, pile `core` + Traefik, images GHCR | à déployer (serveur à choisir) |
| Parcours de bout en bout | test Playwright versionné et lancé par la CI (inscription → stock → idées → génération → chaque onglet) | en place : `tests/test_e2e_parcours.py` + `tests/e2e/parcours.cjs`, job CI `e2e` |
| Démo | page statique en ligne, moteur réel et résultats pré-calculés | en ligne |

Aujourd'hui, la preuve de concept se lance en local avec `docker compose --profile core up`, à partir des
images publiées sur GHCR par `cd.yml`. Le parcours stock → idées → projet → câblage, code, simulation
fonctionne de bout en bout.
