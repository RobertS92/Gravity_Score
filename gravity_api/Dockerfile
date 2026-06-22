# Gravity NIL Intelligence API — production container.
# Railway: Root Directory = gravity_api (default). Sibling packages live in docker-bundle/
# (run scripts/sync_api_docker_bundle.sh before deploy, or use repo-root build below).
#
# Repo-root build (alternative): Root Directory = . , Dockerfile = Dockerfile.gravity-api

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

COPY requirements.txt /app/gravity_api/requirements.txt
RUN pip install -r /app/gravity_api/requirements.txt

RUN apt-get purge -y gcc libpq-dev && apt-get autoremove -y

COPY docker-bundle/gravity_composite /app/gravity_composite
COPY docker-bundle/config /app/config
COPY docker-bundle/gravity_ml /app/gravity_ml
COPY . /app/gravity_api

RUN useradd --create-home --shell /usr/sbin/nologin gravity \
 && chown -R gravity:gravity /app
USER gravity

EXPOSE 8000

CMD ["sh", "-c", "exec uvicorn gravity_api.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
