#!/usr/bin/env bash
# Decrypt SOPS-encrypted vars into the Ansible inventory directory.
# Run before any playbook execution.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SOPS_FILE="$SCRIPT_DIR/vars.sops.yml"
DEST="$SCRIPT_DIR/inventory/host_vars/matrix.nocfa.net/vars.yml"
export SOPS_AGE_KEY_FILE="$SCRIPT_DIR/../../noc-homelab-beads/homelab.agekey"

if [[ ! -f "$SOPS_FILE" ]]; then
  echo "ERROR: $SOPS_FILE not found" >&2
  exit 1
fi

mkdir -p "$(dirname "$DEST")"
sops -d "$SOPS_FILE" > "$DEST"
echo "Decrypted vars to $DEST"
