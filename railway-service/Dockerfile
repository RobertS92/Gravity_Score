FROM python:3.11-slim

WORKDIR /app

# So `import gravity` resolves (gravity/ copied to /app/gravity)
ENV PYTHONPATH=/app

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

# Health check (PORT set at runtime by Railway / compose)
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s \
  CMD sh -c 'curl -fsS "http://127.0.0.1:${PORT:-8000}/health" || exit 1'

# Run FastAPI (one worker so scheduler and healthcheck stay predictable)
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
