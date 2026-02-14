#!/usr/bin/env bash
# FileBot Symlink Creator for Zurg/Real-Debrid (Linux)
# Creates renamed symlinks from /mnt/zurg/{movies,shows} to media/ folder
# Standalone script -- no secrets, no sops needed

set -euo pipefail

REPO_ROOT="/home/noc/noc-homelab"
MOUNT_POINT="/mnt/zurg"
DEST_MOVIES="$REPO_ROOT/media/movies"
DEST_SHOWS="$REPO_ROOT/media/shows"

# Check if mount is available
if ! mountpoint -q "$MOUNT_POINT" 2>/dev/null; then
    echo "ERROR: $MOUNT_POINT is not mounted. Start Zurg and Rclone first." >&2
    exit 1
fi

mkdir -p "$DEST_MOVIES" "$DEST_SHOWS"

echo "=== FileBot Symlink Creator ==="
echo ""

# Process Movies
echo "Processing Movies..."
filebot -rename "$MOUNT_POINT/movies" -r \
    --action symlink \
    --db TheMovieDB \
    -non-strict \
    --format "$DEST_MOVIES/{n} ({y})/{n} ({y})" \
    --def xattr=false \
    --log info

echo ""

# Process TV Shows
echo "Processing TV Shows..."
filebot -rename "$MOUNT_POINT/shows" -r \
    --action symlink \
    --db TheTVDB \
    -non-strict \
    --format "$DEST_SHOWS/{n}/Season {s}/{n} - S{s00}E{e00} - {t}" \
    --def xattr=false \
    --log info

echo ""
echo "=== Done ==="
echo "Symlinks created in: $REPO_ROOT/media/"
echo "Point Emby/Jellyfin libraries at media/movies and media/shows"
