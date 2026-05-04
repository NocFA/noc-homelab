#!/usr/bin/env bash
# Monthly rebuild of the Ireland PMTiles bundle from the Protomaps daily build.
# Writes /home/webdev/tiles/ireland-YYYY-MM-DD.pmtiles atomically.
# Run as User=webdev via pmtiles-rebuild.service.
set -euo pipefail

TILE_DIR="/home/webdev/tiles"
BBOX="-10.5,51.4,-5.4,55.4"          # Ireland (RoI + NI)
PMTILES_BIN="/usr/local/bin/go-pmtiles"

# Find the most recent Protomaps daily build (walk back up to 7 days).
SOURCE_URL=""
SOURCE_DATE=""
for offset in 0 1 2 3 4 5 6 7; do
    d=$(date -u -d "${offset} days ago" +%Y%m%d)
    url="https://build.protomaps.com/${d}.pmtiles"
    if curl -sIfL --max-time 30 "${url}" >/dev/null 2>&1; then
        SOURCE_URL="${url}"
        SOURCE_DATE=$(date -u -d "${offset} days ago" +%Y-%m-%d)
        break
    fi
done

if [ -z "${SOURCE_URL}" ]; then
    echo "ERROR: no Protomaps build found in the last 7 days" >&2
    exit 1
fi

OUT="${TILE_DIR}/ireland-${SOURCE_DATE}.pmtiles"
TMP="${TILE_DIR}/.tmp.ireland-${SOURCE_DATE}.pmtiles"

if [ -f "${OUT}" ]; then
    echo "Up-to-date: ${OUT} already exists, skipping extract."
    exit 0
fi

echo "Extracting ${SOURCE_URL} bbox=${BBOX} -> ${TMP}"
"${PMTILES_BIN}" extract "${SOURCE_URL}" "${TMP}" \
    --bbox="${BBOX}" \
    --download-threads=8

mv -f "${TMP}" "${OUT}"
echo "Wrote ${OUT} ($(stat -c%s "${OUT}") bytes)"
