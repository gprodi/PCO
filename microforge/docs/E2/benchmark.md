# Benchmark des services d'IA (C7)

## Besoin reformulé
| Ensemble fonctionnel | Description |
|---|---|
| F1 Détection | localiser et classer plusieurs composants sur une photo de stock |
| F2 Identification fine | lire les marquages, distinguer DHT11/DHT22, modèles de cartes |
| F3 Génération de code | logique Arduino C++ à partir d'une spécification structurée |
| F4 Raisonnement électronique | explications, guides, idées de projets (le câblage reste déterministe) |
| F5 Embeddings | RAG sur datasheets et cours |

**Contraintes** : budget ≈ 0 € ; local d'abord (RGPD) ; matériel Mac M4 16 Go / GPU 8 Go / GPU 6 Go ;
latence < 5 s par photo ; licence compatible dépôt public ; sobriété énergétique.

## Services étudiés
| Service | F1 | F2 | F3 | F4 | F5 | Coût | Confidentialité | Éco-responsabilité | Prérequis / contraintes |
|---|---|---|---|---|---|---|---|---|---|
| Ultralytics YOLO11/26 (local) | 3 | 1 | – | – | – | 0 € | données locales | très sobre en inférence ; entraînement GPU | dataset annoté ; **AGPL-3.0** |
| RF-DETR N/S/M/L (local) | 3 | 1 | – | – | – | 0 € | locales | sobre | Apache 2.0 ; plus lourd à entraîner |
| Qwen3-VL 4B/8B via Ollama | 1 | 2 | 1 | 2 | – | 0 € | locales | moyen (GPU) | 6–8 Go VRAM / 16 Go unifiés |
| Gemma 3/4 4B–12B via Ollama | 1 | 2 | 1 | 2 | – | 0 € | locales | moyen | idem |
| Qwen3 4B/8B/14B via Ollama | – | – | 2 | 2 | – | 0 € | locales | moyen | idem |
| bge-m3 / nomic-embed-text (Ollama) | – | – | – | – | 3 | 0 € | locales | sobre | < 1 Go |
| Gemini Flash (API, offre gratuite) | 1 | 3 | 3 | 3 | 2 | 0 € (quotas variables) | hors UE, conditions de réutilisation à vérifier | mutualisé, peu documenté | clé d'API |
| Claude Opus 5.5 (API) | 1 | 3 | 3 | 3 | – | payant à l'usage | hors UE ; pas d'entraînement sur les données API | peu documenté | clé d'API, budget |
| Roboflow Hosted Inference | 3 | 1 | – | – | – | gratuit limité | cloud US | — | compte, quotas |

**Non étudiés** (et pourquoi) : AWS Rekognition Custom Labels, Google Vertex AutoML Vision (coût
d'entraînement et d'hébergement incompatibles avec le budget, pas d'exécution locale) ; Azure Custom Vision
(statut de maintenance à vérifier, cloud uniquement) ; GPT-4o/5 (payant, redondant avec Claude/Gemini).

## Mesures (protocole `microforge/benchmark/`)
Résultats insérés après exécution sur les 50 photos de test (`run_benchmark.py`) : précision, rappel, F1,
latence p50/p95, gCO₂e/photo (CodeCarbon), coût/1 000 photos.

## Conclusion et recommandation
- **Retenus** : YOLO (F1, local, entraîné sur nos classes) + **VLM local** Qwen3-VL (F2) via Ollama ;
  Qwen3 pour F3/F4 ; bge-m3 pour F5. Secours : Gemini (offre gratuite) via la passerelle.
- **Écarté** : Claude (payant à l'usage, pas d'abonnement) — le fournisseur reste dans `llm_gateway` mais hors de la chaîne.
- **Écartés** : services cloud d'entraînement (coût, confidentialité), Roboflow hébergé (dépendance cloud).
