#!/bin/sh
# Crée le compartiment S3 des artefacts s'il n'existe pas, puis lance le serveur MLflow.
set -e
python - <<'PY'
import os, time, boto3
s3 = boto3.client("s3", endpoint_url=os.environ["MLFLOW_S3_ENDPOINT_URL"])
for attempt in range(30):
    try:
        if "mlflow" not in [b["Name"] for b in s3.list_buckets().get("Buckets", [])]:
            s3.create_bucket(Bucket="mlflow")
        break
    except Exception as exc:
        print("stockage S3 pas encore prêt :", exc)
        time.sleep(2)
PY
exec mlflow server \
  --backend-store-uri "postgresql://mlflow:${POSTGRES_PASSWORD}@postgres:5432/mlflow" \
  --artifacts-destination s3://mlflow \
  --host 0.0.0.0 --port 5000 \
  --allowed-hosts "localhost,localhost:5000,127.0.0.1,127.0.0.1:5000,mlflow,mlflow:5000"
