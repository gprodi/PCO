# Monitorage de l'application (C20)

Installation : `docker compose --profile monitoring up -d` (cf. `microforge/monitoring/README.md`).

| Métrique | Seuil d'alerte | Outil | Pourquoi |
|---|---|---|---|
| Disponibilité `/health` | panne > 1 min | Uptime Kuma + Prometheus `up` | service rendu |
| Latence p95 | > 2 s (5 min) avertissement | Prometheus / Grafana | expérience utilisateur |
| Erreurs 5xx | > 2 % (5 min) critique | Prometheus | bug ou dépendance en panne |
| Replis LLM | > 10 en 15 min | `mf_llm_calls` | Ollama indisponible |
| Échecs de connexion | > 20/min | Loki (LogQL) | attaque par force brute |
| Taux de corrections modèle | > 25 % | `mf_detection_correction_rate` | qualité du modèle (boucle MLOps) |

**Journalisation** : loguru (JSON en production), identifiant de requête propagé (`X-Request-ID`),
**aucune donnée personnelle** (pas d'e-mail ni de jeton dans les logs), conservation 6 mois.

**Choix d'outillage** : Prometheus/Grafana/Loki/Uptime Kuma (vus en cours, open-source, auto-hébergés,
gratuits) ; Grafana Alloy remplace Promtail (fin de vie 2026).
