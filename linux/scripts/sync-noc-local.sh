#!/usr/bin/env bash
# Pulls latest changes on noc-local and restarts the dashboard.
# Run from noc-tux after pushing changes that affect the dashboard.

set -euo pipefail

HOST="noc@noc-local"
REPO="/Users/noc/noc-homelab"

echo "Pulling latest on noc-local..."
ssh "$HOST" "cd $REPO && git pull"

echo "Restarting dashboard..."
ssh "$HOST" "pkill -f 'python.*app.py' 2>/dev/null || true; cd $REPO/dashboard && nohup python3 app.py > /dev/null 2>&1 &"

echo "Done."
