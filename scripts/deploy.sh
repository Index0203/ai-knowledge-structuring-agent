#!/usr/bin/env sh
# Builds and starts the production stack, then reports where it is reachable.
#
#   sh scripts/deploy.sh
#
# The script is idempotent: run it again after pulling changes to rebuild and
# restart. Data lives in named volumes, so nothing is lost between runs.

set -eu

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example (the stack runs in degraded mode without a model key)."
  echo "Set OPENAI_API_KEY / OPENAI_MODEL / OPENAI_BASE_URL to use a real provider."
fi

echo "Building and starting the production stack..."
docker compose -f docker-compose.prod.yml up -d --build

echo "Waiting for the backend health check..."
attempt=0
healthy=0
while [ "$attempt" -lt 60 ]; do
  sleep 3
  attempt=$((attempt + 1))
  if docker compose -f docker-compose.prod.yml ps --format "{{.Service}} {{.Status}}" | grep -q "backend .*healthy"; then
    healthy=1
    break
  fi
done

docker compose -f docker-compose.prod.yml ps

if [ "$healthy" -eq 1 ]; then
  echo ""
  echo "Deployment ready:"
  echo "  frontend  http://localhost:${FRONTEND_PORT:-3000}"
  echo "  api docs  http://localhost:${BACKEND_PORT:-8000}/docs"
  echo "  logs      docker compose -f docker-compose.prod.yml logs -f backend worker"
  echo "  stop      docker compose -f docker-compose.prod.yml down"
else
  echo "Backend did not become healthy; check the logs:"
  echo "  docker compose -f docker-compose.prod.yml logs backend migrate"
  exit 1
fi
