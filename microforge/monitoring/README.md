# Monitoring MicroForge (C11 modèle, C20 application)

`docker compose --profile monitoring up -d` (dossier `microforge/infra`), avec le profil `core`
pour les API. Puis :

| Outil | URL | Rôle |
|---|---|---|
| Grafana | http://localhost:3000 (admin / `GRAFANA_ADMIN_PASSWORD`, `change-me` par défaut) | tableaux de bord « Application » et « Modèle de vision » ; Alerting > Règles : les alertes de Prometheus et de Loki avec leur état |
| Prometheus | http://localhost:9090 | métriques des deux API (toutes les 15 s) et règles d'alerte (`prometheus/alerts.yml`) |
| Alertmanager | http://localhost:9093 | reçoit les alertes déclenchées, les regroupe, notifie Discord si `DISCORD_WEBHOOK_URL` est fourni |
| Loki + Alloy | Grafana > Explorer (`{service="api_ia"}`) | journaux JSON des conteneurs ; règle d'alerte sur les échecs de connexion (`loki/rules/`) |
| Uptime Kuma | http://localhost:3001 | sondes HTTP `/health` des API et `/_stcore/health` de Streamlit (à configurer dans son interface) |

Notifications Discord : mettre l'adresse du webhook dans `microforge/.env`
(`DISCORD_WEBHOOK_URL=…`, jamais dans le dépôt). Sans elle, rien n'est envoyé : les alertes restent
visibles dans Alertmanager et dans Grafana (`alertmanager/start.sh` choisit la configuration).

## Alertes

| Alerte | Règle | Durée | Gravité | Réaction |
|---|---|---|---|---|
| `APIIndisponible` | `up == 0` (api_data, api_ia) | 1 min | critique | relancer le service, lire ses journaux |
| `LatenceP95Elevee` | p95 > 2 s (histogramme fin, seaux jusqu'à 60 s) | 5 min | avertissement | profil matériel, modèle, base |
| `TauxErreurs5xx` | 5xx > 2 % des requêtes | 5 min | critique | journaux Loki par `request_id` |
| `FallbackLLMFrequent` | plus de 10 replis vers Gemini en 15 min | — | avertissement | Ollama arrêté ou saturé |
| `EchecsConnexionNombreux` (Loki) | plus de 20 « Échec de connexion » par minute | 1 min | avertissement | force brute : bloquer l'adresse, vérifier le limiteur |
| `TauxCorrectionsEleve` | corrections utilisateurs > 25 % (7 jours) | 1 h | avertissement, `action=retrain` | réentraîner (voir plus bas) |
| `ConfianceMoyenneBasse` | confiance moyenne < 0,5 sur 24 h | 2 h | avertissement | dérive des photos : échantillonner, étiqueter |
| `ObjetsInconnusEnHausse` | objets hors catalogue > 20 % de toutes les détections (6 h) | 1 h | info | enrichir le catalogue ou le jeu de données |

Une panne d'API masque les alertes de latence et d'erreurs de la même API (règle d'inhibition
d'Alertmanager) : un seul message pour une seule cause.

**Réentraînement** : `TauxCorrectionsEleve` porte l'étiquette `action=retrain`. Le workflow
`model-cd.yml` se lance par un évènement `repository_dispatch` de type `retrain` :

```bash
gh api repos/gprodi/PCO/dispatches -f event_type=retrain
```

L'envoi automatique depuis Alertmanager n'est pas fait : son webhook n'a pas le format attendu par
GitHub et demanderait un relais muni d'un jeton.

## Tests

- **Règles d'alerte** : `prometheus/alerts.test.yml`, séries synthétiques pour chaque alerte
  (déclenchée au-delà du seuil et après sa durée, muette en dessous) :

  ```bash
  cd microforge/monitoring/prometheus
  docker run --rm -v "$PWD:/p" -w /p --entrypoint promtool prom/prometheus:v3.15.1 test rules alerts.test.yml
  ```

- **Cohérence** : `tests/test_monitoring.py` vérifie que chaque métrique citée par une alerte ou un
  tableau existe dans les `/metrics` des API, que les deux configurations d'Alertmanager ont le même
  routage, que la règle Loki cherche le message réellement écrit par api_data, et que le compose et
  la CI utilisent les mêmes images.
- **CI** (job « Supervision ») : `promtool check config`, `promtool test rules`, `amtool
  check-config`, puis la pile est lancée : Grafana doit démarrer avec ses 2 tableaux et 3 sources,
  Prometheus doit être relié à Alertmanager, Loki doit avoir chargé sa règle.

## Bac à sable (C11 : tester la chaîne avant la production)

`traffic_generator.py` crée un utilisateur, envoie des photos puis des retours :

```bash
uv run python microforge/monitoring/traffic_generator.py --n 20            # trafic normal (10 % de corrections)
uv run python microforge/monitoring/traffic_generator.py --n 20 --drift    # dérive : photos sombres, 60 % de corrections
```

L'analyse de photo est limitée à 30 par heure et par utilisateur (`MF_RATE_LIMIT_VISION`) : pour un
trafic long, relancer le script (un nouvel utilisateur à chaque fois).

## Essai réel du 06/11/2026

Pile lancée sur le poste de développement (Prometheus 3.15.1, Alertmanager 0.34.2, Grafana 13.3.0,
Loki 3.7.9), API lancées avec `uvicorn` (SQLite, modèle de langage simulé `LLM_CHAIN=fake`, donc
détections fictives : confiance nulle, objets tous inconnus). Résultats :

- Grafana démarre, charge les 2 tableaux et les 3 sources ; les cibles api_data et api_ia sont
  `up` ; Prometheus est relié à Alertmanager.
- Trafic `--drift` : taux de corrections mesuré 60 % ; `TauxCorrectionsEleve`,
  `ConfianceMoyenneBasse` et `ObjetsInconnusEnHausse` passent à l'état *pending* (elles ne
  deviennent *firing* qu'après 1 h ou 2 h de dépassement, par construction).
- api_data arrêtée : `APIIndisponible` arrive dans Alertmanager **80 s** après l'arrêt
  (1 min de tolérance + intervalle de collecte).
- 45 « Échec de connexion » par minute poussés dans Loki : `EchecsConnexionNombreux` arrive dans
  Alertmanager **95 s** après le début.

Défauts trouvés par cet essai, corrigés et couverts par un test :

| Défaut | Effet | Correctif |
|---|---|---|
| point de contact Discord provisionné dans Grafana avec une adresse vide par défaut | **Grafana ne démarrait pas** | routage déplacé dans Alertmanager ; Discord seulement si l'adresse est fournie |
| aucun Alertmanager | les alertes de Prometheus n'étaient envoyées nulle part | service `alertmanager`, `alerting` dans `prometheus.yml` |
| latence p95 lue sur l'histogramme par route, dont le dernier seau fini est 1 s | p95 calculé plafonné à 1 s : **l'alerte à 2 s ne pouvait jamais se déclencher** | histogramme `http_request_duration_highr_seconds` (seaux jusqu'à 60 s), alerte et tableau |
| compteurs de détection créés à la première photo | Prometheus ne voit pas ce premier saut : confiance moyenne `NaN` sur faible trafic | séries créées à 0 au démarrage pour chaque source et chaque mode |
| « objets hors catalogue » divisé par les seules détections reconnues | si tout est inconnu (le pire cas), résultat vide : **alerte muette** | division par toutes les détections (`mf_detection_confidence_count`) |
| alerte « échecs de connexion » documentée sans règle | rien ne la calculait | règle Loki (`loki/rules/fake/securite.yml`) envoyée à Alertmanager |

Captures : `docs/E5/img/grafana-application.png`, `docs/E3/img/grafana-modele.png`,
`docs/E5/img/alertmanager.png`.

Reste à faire : envoi réel sur Discord (adresse du webhook à fournir), sondes d'Uptime Kuma, essai
avec Alloy sur les conteneurs (ici les API tournaient hors Docker et les journaux ont été poussés
directement dans Loki), relais automatique vers `repository_dispatch`.
