# syntax=docker/dockerfile:1.7
# Image multi-cibles (api_data, api_ia, streamlit) construite avec uv — cours MLOPS 0.
# docker build -f microforge/Dockerfile --target api_data -t microforge-api-data .

FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv
WORKDIR /app
RUN useradd --create-home --uid 10001 mf

FROM base AS deps
COPY pyproject.toml uv.lock ./
COPY packages/llm_gateway/pyproject.toml packages/llm_gateway/README.md packages/llm_gateway/
COPY microforge/pyproject.toml microforge/README.md microforge/
COPY revision/pyproject.toml revision/
RUN mkdir -p packages/llm_gateway/src/llm_gateway microforge/src/microforge revision/src/revision \
 && touch packages/llm_gateway/src/llm_gateway/__init__.py microforge/src/microforge/__init__.py revision/src/revision/__init__.py \
 && uv sync --frozen --no-dev --package microforge --extra data --extra app --no-install-workspace

FROM deps AS app
COPY packages/llm_gateway packages/llm_gateway
COPY microforge/src microforge/src
RUN uv sync --frozen --no-dev --package microforge --extra data --extra app
ENV PATH="/app/.venv/bin:$PATH"
USER mf

FROM app AS api_data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
CMD ["uvicorn", "microforge.api_data.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]

FROM app AS api_ia
EXPOSE 8001
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')"
CMD ["uvicorn", "microforge.api_ia.main:app", "--host", "0.0.0.0", "--port", "8001", "--proxy-headers"]

FROM app AS streamlit
EXPOSE 8501
WORKDIR /app/microforge/src/microforge/app_streamlit
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"
CMD ["streamlit", "run", "Accueil.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
