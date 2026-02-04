#!/bin/bash
# Beads sync script - bidirectional sync between noc-local and noc-winlocal
# Run this from noc-local to sync issue tracking across machines

set -e

BEADS_DIR="/Users/noc/noc-homelab/.beads"
REMOTE_USER="noc"
REMOTE_HOST="noc-winlocal"
REMOTE_BEADS_DIR="C:/Users/noc/homelab/.beads"

echo "🔄 Syncing beads database between noc-local and $REMOTE_HOST..."

# Step 1: Export both sides to JSONL
echo "📤 Exporting local changes..."
bd sync

echo "📤 Exporting remote changes..."
ssh "$REMOTE_USER@$REMOTE_HOST" "powershell -Command 'cd C:\Users\noc\homelab; bd sync'"

# Step 2: Fetch remote JSONL files
echo "📥 Fetching remote database..."
scp "$REMOTE_USER@$REMOTE_HOST:$REMOTE_BEADS_DIR/issues.jsonl" "$BEADS_DIR/issues.remote.jsonl"
scp "$REMOTE_USER@$REMOTE_HOST:$REMOTE_BEADS_DIR/interactions.jsonl" "$BEADS_DIR/interactions.remote.jsonl" 2>/dev/null || true

# Step 3: Backup and merge (beads handles deduplication on import)
cp "$BEADS_DIR/issues.jsonl" "$BEADS_DIR/issues.local.jsonl"
cat "$BEADS_DIR/issues.local.jsonl" "$BEADS_DIR/issues.remote.jsonl" | sort -u > "$BEADS_DIR/issues.merged.jsonl"
mv "$BEADS_DIR/issues.merged.jsonl" "$BEADS_DIR/issues.jsonl"

# Step 4: Import merged data locally
echo "📥 Importing merged data..."
bd sync --import

# Step 5: Export merged data and push to remote
echo "📤 Exporting merged data..."
bd sync

echo "📤 Pushing to $REMOTE_HOST..."
scp "$BEADS_DIR/issues.jsonl" "$REMOTE_USER@$REMOTE_HOST:$REMOTE_BEADS_DIR/issues.jsonl"
scp "$BEADS_DIR/interactions.jsonl" "$REMOTE_USER@$REMOTE_HOST:$REMOTE_BEADS_DIR/interactions.jsonl" 2>/dev/null || true

# Step 6: Import on remote
echo "📥 Importing on $REMOTE_HOST..."
ssh "$REMOTE_USER@$REMOTE_HOST" "powershell -Command 'cd C:\Users\noc\homelab; bd sync --import'"

# Cleanup temp files
rm -f "$BEADS_DIR/issues.local.jsonl" "$BEADS_DIR/issues.remote.jsonl"

echo "✅ Sync complete! Both machines now have identical beads databases."
