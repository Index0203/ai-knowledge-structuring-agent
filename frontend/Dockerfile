FROM node:20-alpine AS deps
WORKDIR /app
RUN corepack enable
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# Development image: docker-compose.yml bind-mounts the source and Next.js hot-reloads.
FROM deps AS dev
COPY . .
EXPOSE 3000
CMD ["pnpm", "run", "dev", "--hostname", "0.0.0.0"]

# Production build. NEXT_PUBLIC_* values are inlined into the client bundle here, so the
# API address used by the browser has to be provided as a build argument.
FROM deps AS build
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL \
    NEXT_TELEMETRY_DISABLED=1
COPY . .
RUN pnpm run build

# Production image: the standalone server plus static assets, running unprivileged.
FROM node:20-alpine AS prod
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
RUN addgroup -g 10001 app && adduser -u 10001 -G app -D app
COPY --from=build --chown=app:app /app/.next/standalone ./
COPY --from=build --chown=app:app /app/.next/static ./.next/static
USER app
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:3000/ || exit 1
CMD ["node", "server.js"]
