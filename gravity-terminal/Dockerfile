# Production static hosting for the Vite SPA (Railway, Fly, ECS, etc.).
# Local build:
#   docker build --build-arg VITE_API_URL=https://your-api.up.railway.app/v1 -t gravity-terminal .
# Railway: add service variable VITE_API_URL (same name as ARG below). Railway injects service variables
# into the Docker build for matching ARG declarations.
# https://docs.railway.com/builds/dockerfiles#using-variables-at-build-time

FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Must be a real origin with a hostname (see `getApiBaseUrl` in src/api/client.ts), e.g. https://api.up.railway.app/v1
ARG VITE_API_URL
RUN if [ -z "$VITE_API_URL" ]; then \
      echo "ERROR: VITE_API_URL is empty. On Railway, set Variables → VITE_API_URL on this service, then redeploy." >&2; exit 1; \
    fi; \
    if ! echo "$VITE_API_URL" | grep -qE '^https?://[^/]+'; then \
      echo "ERROR: VITE_API_URL must include a hostname (example: https://your-api.up.railway.app/v1)." >&2; \
      echo "Got: $VITE_API_URL" >&2; \
      echo "If you see https:///v1, the API service reference (RAILWAY_PUBLIC_DOMAIN) did not resolve at build time: enable Networking on the API service first, or set VITE_API_URL to the full HTTPS API URL (no template)." >&2; \
      exit 1; \
    fi
ENV VITE_API_URL=${VITE_API_URL}
RUN npm run build

FROM node:22-alpine AS runtime
WORKDIR /app
RUN npm install -g serve@14.2.4
COPY --from=build /app/dist ./dist
ENV NODE_ENV=production
EXPOSE 3000
# Railway and others set PORT; serve listens on all interfaces.
CMD ["sh", "-c", "exec serve -s dist -l ${PORT:-3000}"]
