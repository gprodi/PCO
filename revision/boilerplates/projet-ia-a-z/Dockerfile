# Une image pour les trois services Python ; docker compose choisit la commande.
FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1 PATH="/app/.venv/bin:$PATH"
WORKDIR /app
COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev --no-install-project --extra pgvector
COPY . .
RUN useradd --uid 10001 --no-create-home app && chown -R app /app
USER app
CMD ["uvicorn", "api_ia.main:app", "--host", "0.0.0.0", "--port", "8001"]
