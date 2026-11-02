# La Forge MLOps (Kubernetes, KEDA & Observabilité)

## Contexte du Projet

Vous disposez d'une application de prédiction asynchrone (FastAPI + Streamlit + Celery + RabbitMQ). Votre mission est d'industrialiser cette solution en intégrant les piliers du MLOps : **le monitoring, la traçabilité des modèles et la qualité logicielle.**

---

## Étape 1 : Consolidation & Qualité (Local)

Avant de déployer, nous devons garantir que le code est robuste.

1. **Logging avec Loguru** : Remplacez tous vos `print()` par des logs structurés. Configurez un format incluant le timestamp et le niveau (INFO/ERROR). Ces logs seront capturés par Kubernetes plus tard.
2. **Tests unitaires (Pytest)** : Créez un dossier `/tests`. Écrivez des tests pour vérifier que l'API répond bien `200 OK` et que le worker reçoit bien les tâches.
3. **Couverture (Pytest-cov)** : Votre pipeline doit exiger au moins **80% de couverture** pour autoriser le build de l'image Docker.

---

## Étape 2 : Le "Tout-en-un" avec Docker Compose

Créez un fichier `docker-compose.full.yml` pour valider l'interopérabilité des services :

* **Infrastructure de base** : `api`, `front`, `worker`, `rabbitmq`, `redis`, `flower`.
* **MLflow** : Ajoutez un service `mlflow-server` (utilisant SQLite en backend local). Modifiez le `worker.py` pour qu'il récupère le modèle via `mlflow.pyfunc.load_model()`. Le Model Registry (`minio`) est une base de données centralisée qui gère le cycle de vie des modèles ; on y "tague" le meilleur modèle avec un Alias (ex: @production) via l'UI ou l'API, permettant aux workers de charger dynamiquement cette version sans jamais modifier le code source.
* **Monitoring** :
* `prometheus` : Configuré pour scraper RabbitMQ (via l'exporter) et l'API. Prometheus utilise le Plugin Prometheus de RabbitMQ pour transformer les statistiques internes de la file en métriques formatées, qu'il vient "scrapper" (aspirer) périodiquement via une requête HTTP sur le port 15692 pour alimenter les dashboards et les alertes.
* `grafana` : Connecté à Prometheus.
* `uptime-kuma` : Pour surveiller la disponibilité de l'API et du Front.



---

## Étape 3 : Migration vers Kubernetes (Le Découpage)

Une fois le Compose validé, passez à Kubernetes. Pour ne pas vous perdre, utilisez la structure de dossiers suivante :

### `/k8s/01-core` (L'essentiel)

* `01_rabbitmq.yaml` le broker de celery
* `01_redis.yaml` la mémoire
* `03_api.yaml` (Deployment + Service)
* `04_worker.yaml` (Deployment uniquement)
* `05_front.yaml` (Deployment + Service)

### `/k8s/02-ml-ops` (L'intelligence)

* `01_postgresql.yaml` : le Back End store à accès simultané
* `02_minio.yaml` : Pour le Storage d'artefact (Artifact Store).
* `03_mlflow.yaml` : Déployez MLflow avec un `PersistentVolume` pour ne pas perdre vos modèles au redémarrage.


* **Mise à jour immédiate** : Modifiez les variables d'environnement de vos Pods API/Worker pour pointer vers l'URL interne `http://mlflow-service:5000`.

### `/k8s/03-scaling` (La performance)

* `01_keda-autoscaler.yaml` : Configurez le `ScaledObject` pour observer la queue RabbitMQ.
* **Réglage fin** : Ajustez la `cooldownPeriod` pour éviter que les workers ne s'éteignent trop vite.

### `/k8s/04-monitoring` (La visibilité)

* `01_prometheus-stack.yaml` : Installez Prometheus et les "Exporters" (pour RabbitMQ et les métriques des Pods).
* `02_grafana.yaml` : Créez un dashboard montrant :
1. Le nombre de messages en attente (RabbitMQ).
2. Le nombre de workers actifs (KEDA).
3. Le temps de réponse de l'API.


* `03_uptime-kuma.yaml` : Configurez des sondes HTTP sur `http://api:8000/health` et `http://localhost:8501/healthz`.
* `04_flower.yaml` : pour monitorer celery.

---

## Objectifs Pédagogiques (Ce que vous devez démontrer)

### 1. Le "Self-Healing"

Si vous tuez un pod MLflow ou API (`kubectl delete pod...`), montrez que Kubernetes le relance instantanément sans perte de service.

### 2. Le "Blue-Green" simplifié

Expliquez comment modifier la version de l'image dans `03_api.yaml` et comment Kubernetes effectue un "Rolling Update" (il ne coupe l'ancienne version que quand la nouvelle est prête).

### 3. Le Monitoring en boucle fermée

* Lancez 50 prédictions via le Front.
* Montrez sur **Grafana** la courbe de RabbitMQ monter.
* Montrez sur **Flower** ou `kubectl get pods` les workers spawner grâce à **KEDA**.
* Vérifiez sur **Uptime Kuma** que le service reste stable malgré la charge.

---

## Conseils pour réussir

* **Ordre de déploiement** : Commencez toujours par RabbitMQ et Redis. Sans eux, l'API et le Worker crasheront en boucle.
* **Noms DNS** : Rappelez-vous que dans Kubernetes, le `metadata.name` d'un Service devient son URL. Exemple : un service nommé `mlflow` est accessible via `http://mlflow:5000`.
* **Variables d'environnement** : Centralisez vos URLs (Broker, Backend, MLflow) dans les `env:` de vos fichiers YAML.

