# Seryvon — image du cœur Python (API, workers, CLI).
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dépendances système minimales (psycopg binaire, build léger).
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Couche de dépendances (cache) : on copie d'abord les métadonnées du paquet.
COPY pyproject.toml README.md LICENSE NOTICE ./
COPY src ./src
RUN pip install --upgrade pip && pip install -e .

# Le reste du code (migrations, config).
COPY alembic.ini ./
COPY alembic ./alembic

# Utilisateur non-root.
RUN useradd --create-home --uid 10001 seryvon
USER seryvon

EXPOSE 8000

# Par défaut : API. Les workers surchargent la commande dans docker-compose.
CMD ["uvicorn", "seryvon.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ---------------------------------------------------------------------------
# Stage worker-cpu : ajoute Playwright + Chromium pour le rendu SSR (geo.ssr).
# Séparé de l'image API pour ne pas alourdir celle-ci.
# ---------------------------------------------------------------------------
FROM base AS worker

USER root
RUN pip install "playwright>=1.44" \
    && playwright install chromium --with-deps \
    && rm -rf /var/lib/apt/lists/*
USER seryvon
