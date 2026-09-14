# syntax=docker/dockerfile:1

FROM node:20-slim AS base
WORKDIR /app

# ---- Dependencies -----------------------------------------------------
FROM base AS deps
COPY package.json package-lock.json ./
RUN npm ci

# ---- Build --------------------------------------------------------------
FROM base AS builder
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# NEXT_PUBLIC_* vars must be present at build time — they're inlined into
# the client bundle, not read at runtime like server-only env vars.
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
RUN npm run build

# ---- Runtime ---------------------------------------------------------------
FROM base AS runtime
ENV NODE_ENV=production

# curl is not present in node:20-slim by default - installed explicitly
# for the HEALTHCHECK below, same pattern as backend/Dockerfile.
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system app && useradd --system --gid app --no-create-home app

COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json

RUN chown -R app:app /app
USER app

EXPOSE 3000

# Found missing during the Week 12 deployment review - backend/Dockerfile
# has always had a real HEALTHCHECK; this one never did. Checks the root
# page rather than a dedicated /health route, since Next.js has no
# built-in health endpoint and this app doesn't define one - a 200 here
# means the Next.js server process is genuinely serving real HTTP
# responses, not just that the container process is alive.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:3000/ || exit 1

CMD ["npm", "start"]
