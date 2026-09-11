# Seryvon — image du cœur Python (API, workers, CLI).
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dépendances système minimales (psycopg binaire, build léger).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       curl libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b \
    && rm -rf /var/lib/apt/lists/*

# Couche de dépendances (cache) : on copie d'abord les métadonnées du paquet.
COPY pyproject.toml README.md LICENSE NOTICE ./
COPY src ./src
RUN pip install --upgrade pip && pip install -e ".[pdf]"

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
# Stage test : dépendances de développement et tests backend.
# Non utilisée par les services runtime ; elle permet une validation complète
# dans Docker, notamment pour WeasyPrint et ses bibliothèques natives.
# ---------------------------------------------------------------------------
FROM base AS test

USER root
# The base stage already contains the production PDF runtime. Install only
# development tools here so the test stage reuses the expensive PDF layer.
RUN pip install ".[dev]"
COPY tests ./tests
ENV SERYVON_TEST_DATABASE_URL=postgresql+psycopg://seryvon:seryvon@postgres:5432/seryvon
USER seryvon
CMD ["python", "-m", "pytest", "-q"]

# ---------------------------------------------------------------------------
# Stage worker-cpu : ajoute Playwright + Chromium pour le rendu SSR (geo.ssr).
# Séparé de l'image API pour ne pas alourdir celle-ci.
# ---------------------------------------------------------------------------
FROM base AS worker

# Install Playwright system deps (requires root / apt-get), then the Python
# package.  The browser binary itself must be installed as the runtime user
# so Playwright finds it under /home/seryvon/.cache/ms-playwright/.
USER root
RUN pip install "playwright>=1.44" \
    && playwright install-deps chromium \
    && rm -rf /var/lib/apt/lists/*

USER seryvon
RUN playwright install chromium
