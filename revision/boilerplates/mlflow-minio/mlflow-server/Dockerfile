FROM ghcr.io/mlflow/mlflow:v3.17.2
RUN pip install --no-cache-dir psycopg2-binary boto3
COPY entrypoint.sh /entrypoint.sh
ENTRYPOINT ["sh", "/entrypoint.sh"]
