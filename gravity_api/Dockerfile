# Gravity NIL Intelligence API — production container.
#
# Railway (recommended): Root Directory = gravity_api , Dockerfile = Dockerfile
#   Monorepo siblings are vendored in docker-bundle/ (scripts/sync_api_docker_bundle.sh).
#
# Alternative: Root Directory = . , Dockerfile = Dockerfile.gravity-api (repo root)

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates gcc libpq-dev \
 && rm -rf /var/lib/apt/lists/*

# Copy full build context once, then resolve layout for gravity_api/ vs repo-root contexts.
COPY . /tmp/build-context

RUN set -eux; \
    mkdir -p /app/gravity_api; \
    if [ -f /tmp/build-context/requirements.txt ]; then \
      cp /tmp/build-context/requirements.txt /app/gravity_api/requirements.txt; \
    elif [ -f /tmp/build-context/gravity_api/requirements.txt ]; then \
      cp /tmp/build-context/gravity_api/requirements.txt /app/gravity_api/requirements.txt; \
    else \
      echo "ERROR: gravity_api requirements.txt not found in build context"; \
      exit 1; \
    fi

RUN pip install -r /app/gravity_api/requirements.txt

RUN apt-get purge -y gcc libpq-dev && apt-get autoremove -y

RUN set -eux; \
    for pkg in gravity_composite gravity_ml config; do \
      if [ -d "/tmp/build-context/docker-bundle/$pkg" ]; then \
        src="/tmp/build-context/docker-bundle/$pkg"; \
      elif [ -d "/tmp/build-context/gravity_api/docker-bundle/$pkg" ]; then \
        src="/tmp/build-context/gravity_api/docker-bundle/$pkg"; \
      elif [ -d "/tmp/build-context/$pkg" ]; then \
        src="/tmp/build-context/$pkg"; \
      else \
        echo "ERROR: missing monorepo package '$pkg' (sync docker-bundle or set repo-root build)"; \
        exit 1; \
      fi; \
      cp -a "$src" "/app/$pkg"; \
    done; \
    if [ -f /tmp/build-context/main.py ]; then \
      cp -a /tmp/build-context/. /app/gravity_api/; \
    elif [ -d /tmp/build-context/gravity_api ]; then \
      cp -a /tmp/build-context/gravity_api/. /app/gravity_api/; \
    else \
      echo "ERROR: gravity_api source not found in build context"; \
      exit 1; \
    fi; \
    rm -rf /app/gravity_api/docker-bundle /tmp/build-context

RUN python -c "from gravity_composite.composite import compute_gravity_raw; print('gravity_composite import OK')"

RUN useradd --create-home --shell /usr/sbin/nologin gravity \
 && chown -R gravity:gravity /app
USER gravity

EXPOSE 8000

CMD ["sh", "-c", "exec uvicorn gravity_api.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
