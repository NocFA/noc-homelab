#!/usr/bin/env bash
# git-autopull.sh — poll Codeberg for changes and pull if new commits exist
# noc-local version: runs via launchd (com.noc.git-autopull)

REPO="/Users/noc/noc-homelab"
REMOTE="origin"  # origin = Codeberg on noc-local
BRANCH="main"
LOG_TAG="git-autopull"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$LOG_TAG] $*"; }

cd "$REPO" || { log "ERROR: repo not found at $REPO"; exit 1; }

# Safety gate: only auto-pull when sitting on the target branch. On a
# feature branch HEAD will always differ from origin/main, so without
# this check we'd enter the "new commits" path and run
# `git checkout -- .` every 5 minutes — silently reverting any
# uncommitted work-in-progress on tracked files.
CURRENT_BRANCH="$(git symbolic-ref --short HEAD 2>/dev/null || echo '')"
if [ "$CURRENT_BRANCH" != "$BRANCH" ]; then
    log "on branch '$CURRENT_BRANCH' (not '$BRANCH') — skipping auto-pull"
    exit 0
fi

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

# Only proceed if we're strictly behind the remote — i.e. HEAD is an
# ancestor of FETCH_HEAD, so a fast-forward is actually possible.
# Guards two cases:
#   - HEAD is ahead of or equal to remote (merged locally, nothing to do)
#   - HEAD has diverged (separate history; pulling would need a merge).
# In either case the old script would still run `git checkout -- .`,
# silently nuking uncommitted tracked changes. We refuse instead.
if ! git merge-base --is-ancestor "$LOCAL" "$REMOTE_SHA" 2>/dev/null; then
    log "HEAD is not an ancestor of $REMOTE/$BRANCH — refusing to auto-pull (would require merge)"
    exit 0
fi

log "new commits detected, pulling from $REMOTE/$BRANCH"

# Discard any local modifications to tracked files (settings live in services.json, not git)
git checkout -- . 2>/dev/null || true

if git pull --ff-only "$REMOTE" "$BRANCH" 2>&1; then
    log "pulled successfully ($(git rev-parse --short HEAD))"
else
    log "ERROR: pull failed (diverged history or conflicts)"
    exit 1
fi

# Pull noc-homelab-beads (memory + beads issues)
BEADS_REPO="$REPO/noc-homelab-beads"
if [ -d "$BEADS_REPO/.git" ]; then
    BEADS_BRANCH="$(git -C "$BEADS_REPO" symbolic-ref --short HEAD 2>/dev/null || echo '')"
    if [ "$BEADS_BRANCH" != "main" ]; then
        log "beads: on branch '$BEADS_BRANCH' (not 'main') — skipping auto-pull"
    elif git -C "$BEADS_REPO" fetch origin main 2>/dev/null; then
        BEADS_LOCAL=$(git -C "$BEADS_REPO" rev-parse HEAD 2>/dev/null)
        BEADS_REMOTE=$(git -C "$BEADS_REPO" rev-parse FETCH_HEAD 2>/dev/null)
        if [ "$BEADS_LOCAL" != "$BEADS_REMOTE" ] && \
           git -C "$BEADS_REPO" merge-base --is-ancestor "$BEADS_LOCAL" "$BEADS_REMOTE" 2>/dev/null; then
            git -C "$BEADS_REPO" checkout -- . 2>/dev/null || true
            if git -C "$BEADS_REPO" pull --ff-only origin main 2>&1; then
                log "beads: pulled successfully ($(git -C "$BEADS_REPO" rev-parse --short HEAD))"
            else
                log "beads: ERROR: pull failed"
            fi
        fi
    else
        log "beads: fetch failed (network or auth)"
    fi
fi
