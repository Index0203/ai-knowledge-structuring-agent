#!/usr/bin/env sh
# Start the development stack (bind mounts + hot reload).

set -eu

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example. Review the values before using external AI providers."
fi

docker compose up --build
