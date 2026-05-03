#!/usr/bin/env bash
# Pull latest Seafile images and restart.
set -euo pipefail

cd "$(dirname "$0")"

docker compose pull
docker compose up -d --remove-orphans
