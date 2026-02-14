#!/usr/bin/env bash
# Deploy Authentik SSO. Generates secrets on first run.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

ENV_FILE="$SCRIPT_DIR/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Generating secrets..."
  PG_PASS=$(openssl rand -base64 36 | tr -d '\n/+=')
  SECRET_KEY=$(openssl rand -base64 60 | tr -d '\n/+=')
  cat > "$ENV_FILE" <<EOF
PG_PASS=$PG_PASS
AUTHENTIK_SECRET_KEY=$SECRET_KEY
EOF
  echo "Created $ENV_FILE"
else
  echo ".env already exists, skipping generation"
fi

docker compose up -d

echo ""
echo "Authentik is starting. Initial setup at:"
echo "  https://auth.nocfa.net/if/flow/initial-setup/"
