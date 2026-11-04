FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv
WORKDIR /srv
COPY pyproject.toml ./
RUN uv sync --no-dev --no-install-project
COPY . .
ENV PATH="/srv/.venv/bin:$PATH" LOG_JSON=1
USER nobody
