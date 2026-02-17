#!/usr/bin/env bash
# git-autopull.sh — poll Codeberg for changes and pull if new commits exist
# noc-local version: runs via launchd (com.noc.git-autopull)

REPO="/Users/noc/noc-homelab"
REMOTE="origin"  # origin = Codeberg on noc-local
BRANCH="main"
LOG_TAG="git-autopull"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$LOG_TAG] $*"; }

cd "$REPO" || { log "ERROR: repo not found at $REPO"; exit 1; }

# Fetch from Codeberg (silent on network errors)
if ! git fetch "$REMOTE" "$BRANCH" 2>/dev/null; then
    log "fetch failed (network error or auth)"
    exit 0
fi

LOCAL=$(git rev-parse HEAD 2>/dev/null)
REMOTE_SHA=$(git rev-parse "FETCH_HEAD" 2>/dev/null)

if [ "$LOCAL" = "$REMOTE_SHA" ]; then
    exit 0  # Already up to date
fi

log "new commits detected, pulling from $REMOTE/$BRANCH"

if git pull --ff-only "$REMOTE" "$BRANCH" 2>&1; then
    log "pulled successfully ($(git rev-parse --short HEAD))"
else
    log "ERROR: pull failed (diverged history or conflicts)"
    exit 1
fi
