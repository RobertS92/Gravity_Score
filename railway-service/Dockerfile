FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (better caching)
COPY railway-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY railway-service/app/ ./app/
COPY gravity/ ./gravity/

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s \
  CMD curl -f http://localhost:$PORT/health || exit 1

# Run FastAPI
CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 2
