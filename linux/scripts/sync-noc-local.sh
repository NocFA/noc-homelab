#!/usr/bin/env bash
# Pulls latest changes on noc-local, restarts dashboard, and reloads agent.
# Run from noc-tux after pushing changes that affect the dashboard or agent config.

set -euo pipefail

HOST="noc@noc-local"
REPO="/Users/noc/noc-homelab"
AGENT_DIR="/home/noc/noc-homelab/agent"

echo "Pulling latest on noc-local..."
ssh "$HOST" "cd $REPO && git pull"

echo "Restarting dashboard..."
ssh "$HOST" "pkill -f 'python.*app.py' 2>/dev/null || true; cd $REPO/dashboard && nohup python3 app.py > /dev/null 2>&1 &"

echo "Reloading agent on noc-tux..."
pkill -f 'python.*agent.py' 2>/dev/null || true
sleep 1
nohup /usr/bin/python3 "$AGENT_DIR/agent.py" --port 8080 --config "$AGENT_DIR/config.yaml" > /tmp/noc-agent.log 2>&1 &

echo "Done."
