# Gravity NIL Intelligence API — production container (FastAPI + uvicorn).
# Build context MUST be the repo root so `gravity_api/` and `migrations/` are both copied.
# Railway: set the service's Root Directory to `/` (repo root) and Dockerfile Path to
# `gravity_api/Dockerfile`. See gravity_api/railway.toml.

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps: only what's needed at build/runtime.
# - ca-certificates: TLS to Supabase / Anthropic
# - libpq-dev + gcc: compile asyncpg wheels if no prebuilt one matches the platform
# Removed after install to keep the image small.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates gcc libpq-dev \
 && rm -rf /var/lib/apt/lists/*

COPY requirements-gravity-api.txt ./
RUN pip install -r requirements-gravity-api.txt

# Strip build-only packages after wheel install.
RUN apt-get purge -y gcc libpq-dev && apt-get autoremove -y

COPY gravity_api ./gravity_api
COPY migrations ./migrations

# Drop privileges.
RUN useradd --create-home --shell /usr/sbin/nologin gravity \
 && chown -R gravity:gravity /app
USER gravity

EXPOSE 8000

# Railway injects $PORT at runtime; fall back to 8000 for local `docker run`.
# sh -c is required because Railway's CMD parser does not expand $PORT otherwise.
CMD ["sh", "-c", "exec uvicorn gravity_api.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
