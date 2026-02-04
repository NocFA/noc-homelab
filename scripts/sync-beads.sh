#!/bin/bash
# Beads sync script - syncs issues between noc-local and noc-winlocal

set -e

BEADS_DIR="/Users/noc/noc-homelab/.beads"
REMOTE_USER="noc"
REMOTE_HOST="noc-winlocal"
REMOTE_BEADS_DIR="C:/Users/noc/homelab/.beads"

echo "Syncing beads database..."

# Export local changes to JSONL
bd sync

# Push local JSONL to remote
echo "Pushing to $REMOTE_HOST..."
scp "$BEADS_DIR/issues.jsonl" "$REMOTE_USER@$REMOTE_HOST:$REMOTE_BEADS_DIR/issues.jsonl"
scp "$BEADS_DIR/interactions.jsonl" "$REMOTE_USER@$REMOTE_HOST:$REMOTE_BEADS_DIR/interactions.jsonl" 2>/dev/null || true

# Import on remote
ssh "$REMOTE_USER@$REMOTE_HOST" "powershell -Command 'cd C:\Users\noc\homelab; bd sync --import'"

# Pull remote changes and import
echo "Pulling from $REMOTE_HOST..."
scp "$REMOTE_USER@$REMOTE_HOST:$REMOTE_BEADS_DIR/issues.jsonl" "$BEADS_DIR/issues.jsonl.remote"
scp "$REMOTE_USER@$REMOTE_HOST:$REMOTE_BEADS_DIR/interactions.jsonl" "$BEADS_DIR/interactions.jsonl.remote" 2>/dev/null || true
mv "$BEADS_DIR/issues.jsonl.remote" "$BEADS_DIR/issues.jsonl"
[ -f "$BEADS_DIR/interactions.jsonl.remote" ] && mv "$BEADS_DIR/interactions.jsonl.remote" "$BEADS_DIR/interactions.jsonl"

bd sync --import

echo "Sync complete!"
