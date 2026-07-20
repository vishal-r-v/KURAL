# Multi-stage build for the React + Vite citizen website.
# Production runtime uses the project's own server.ts (bundled as dist/server.cjs),
# which serves the Vite build from ./dist — no nginx required.
#
# VITE_API_BASE_URL is baked in at build time (browser calls this URL directly).
# For local docker compose, pass http://localhost:8000 so the host browser
# can reach the published backend port.

# Node 20+: @tailwindcss/oxide and @vitejs/plugin-react require it.
FROM node:20-slim AS build

WORKDIR /app

COPY package.json package-lock.json ./
# Fresh install so optional native bindings (@tailwindcss/oxide-*) match Linux.
RUN npm ci && npm rebuild @tailwindcss/oxide || true

# Browser-facing API URL — must be reachable from the user's machine, not
# the Docker-internal hostname (e.g. http://localhost:8000, not http://backend:8000).
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

COPY . .
RUN npm run build

# ── runtime ──────────────────────────────────────────────────────────────
FROM node:20-slim AS runtime

WORKDIR /app

ENV NODE_ENV=production \
    PORT=3000

COPY package.json package-lock.json ./
RUN npm ci --omit=dev

COPY --from=build /app/dist ./dist
# Self-hosted Tamil fonts referenced as /fonts/*.woff2 from index.css
COPY --from=build /app/public ./public

EXPOSE 3000

CMD ["node", "dist/server.cjs"]
