#!/usr/bin/env bash
# Weekly auto-update for Matrix homeserver.
# Pulls latest playbook, updates roles, re-runs setup.
set -euo pipefail

PLAYBOOK_DIR="/home/noc/matrix-docker-ansible-deploy"
HOMELAB_DIR="/home/noc/noc-homelab"
JUST="$HOME/.local/bin/just"
ANSIBLE="$HOME/.local/bin/ansible-playbook"

# Decrypt vars
"$HOMELAB_DIR/services/matrix/deploy-vars.sh"

cd "$PLAYBOOK_DIR"

# Pull latest playbook
git pull --ff-only

# Update roles
"$JUST" roles

# Run setup (idempotent — won't restart unchanged containers)
"$ANSIBLE" -i inventory/hosts setup.yml --tags=setup-all,ensure-matrix-users-created,start
