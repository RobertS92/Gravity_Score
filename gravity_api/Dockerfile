# Gravity NIL Intelligence API — production container (FastAPI + uvicorn).
# Self-contained: build context = this folder (gravity_api/).
# Railway: set the service's Root Directory to `gravity_api` and Railway auto-detects this Dockerfile.

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps: TLS + compilers for any wheel fallback. Stripped after install.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates gcc libpq-dev \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install -r requirements.txt

RUN apt-get purge -y gcc libpq-dev && apt-get autoremove -y

# The package must live at gravity_api/ inside the image so `import gravity_api.main` resolves.
COPY . ./gravity_api

RUN useradd --create-home --shell /usr/sbin/nologin gravity \
 && chown -R gravity:gravity /app
USER gravity

EXPOSE 8000

CMD ["sh", "-c", "exec uvicorn gravity_api.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
