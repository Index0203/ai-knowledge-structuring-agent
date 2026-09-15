#!/usr/bin/env sh
# Stop the development stack. Data volumes are kept.

set -eu
docker compose down
