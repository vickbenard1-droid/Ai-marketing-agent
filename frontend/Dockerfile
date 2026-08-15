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

RUN groupadd --system app && useradd --system --gid app --no-create-home app

COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json

RUN chown -R app:app /app
USER app

EXPOSE 3000
CMD ["npm", "start"]
