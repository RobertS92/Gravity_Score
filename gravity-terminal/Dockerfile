# Production static hosting for the Vite SPA (Railway, Fly, ECS, etc.).
# API URL is applied at container start (see docker-entrypoint.sh) so Railway service references
# resolve at runtime even when they are empty during `docker build`.
# Optional build-time bake: docker build --build-arg VITE_API_URL=https://api.example/v1 -t gravity-terminal .
# Railway: set Variables → VITE_API_URL on this service (runtime). Same variable is used by the entrypoint.

FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ARG VITE_API_URL=
ENV VITE_API_URL=${VITE_API_URL}
RUN npm run build

FROM node:22-alpine AS runtime
WORKDIR /app
RUN npm install -g serve@14.2.4
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh
COPY --from=build /app/dist ./dist
ENV NODE_ENV=production
EXPOSE 3000
ENTRYPOINT ["/docker-entrypoint.sh"]
# Railway sets PORT; serve listens on all interfaces.
CMD ["sh", "-c", "exec serve -s dist -l ${PORT:-3000}"]
