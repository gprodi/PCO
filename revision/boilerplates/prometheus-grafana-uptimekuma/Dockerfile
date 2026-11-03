FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv
WORKDIR /srv
COPY pyproject.toml ./
RUN uv sync --no-dev --no-install-project
COPY app ./app
ENV PATH="/srv/.venv/bin:$PATH"
USER nobody
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
