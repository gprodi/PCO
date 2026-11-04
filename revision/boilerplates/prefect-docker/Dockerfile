FROM prefecthq/prefect:3-latest
WORKDIR /opt/prefect/flows
COPY pyproject.toml ./
RUN pip install --no-cache-dir "httpx>=0.28"
COPY etl ./etl
COPY flows ./flows
