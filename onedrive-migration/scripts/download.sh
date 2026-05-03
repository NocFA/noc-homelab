#!/usr/bin/env bash
set -euo pipefail

# Bulk-download the entire OneDrive account into ./download/
# Requires: `rclone config` to have created a remote named "onedrive".

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${ROOT}/download"
LOG="${ROOT}/logs/rclone-$(date +%Y%m%d-%H%M%S).log"

mkdir -p "$DEST" "$(dirname "$LOG")"

exec rclone copy onedrive: "$DEST" \
  --transfers 8 \
  --checkers 16 \
  --tpslimit 10 \
  --retries 10 \
  --low-level-retries 20 \
  --onedrive-chunk-size 100M \
  --fast-list \
  --progress \
  --stats 30s \
  --log-file "$LOG" \
  --log-level INFO
