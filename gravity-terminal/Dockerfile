# Production static hosting for the Vite SPA (Railway, Fly, ECS, etc.).
# Build with your API origin baked in, e.g.:
#   docker build --build-arg VITE_API_URL=https://your-api.up.railway.app/v1 -t gravity-terminal .
# Railway: set VITE_API_URL in the service Variables and add a Dockerfile build ARG binding in the dashboard,
# or use Railway's "Dockerfile ARG" from the same variable name.

FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Must include `/v1` suffix (see `getApiBaseUrl` in src/api/client.ts), e.g. https://api.example.com/v1
ARG VITE_API_URL
RUN if [ -z "$VITE_API_URL" ]; then \
      echo "ERROR: pass --build-arg VITE_API_URL=https://your-api-host/v1" >&2; exit 1; \
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
