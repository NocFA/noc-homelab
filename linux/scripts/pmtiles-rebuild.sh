#!/usr/bin/env bash
# Monthly rebuild of the Ireland PMTiles bundle in OpenMapTiles schema.
# Source: Geofabrik OSM PBF for Ireland and Northern Ireland.
# Tool:   tilemaker (built from source at /opt/tilemaker, binary at /usr/local/bin/tilemaker).
# Output: /home/webdev/tiles/ireland-YYYY-MM-DD-omt.pmtiles (atomic mv from build dir).
# Run as User=webdev via pmtiles-rebuild.service.
set -euo pipefail

TILE_DIR="/home/webdev/tiles"
BUILD_DIR="${TILE_DIR}/build"
TILEMAKER_BIN="/usr/local/bin/tilemaker"
TILEMAKER_RES="/opt/tilemaker/resources"
PBF_URL="https://download.geofabrik.de/europe/ireland-and-northern-ireland-latest.osm.pbf"

DATE_TAG="$(date -u +%Y-%m-%d)"
PBF="${BUILD_DIR}/ireland-and-northern-ireland-latest.osm.pbf"
TMP_OUT="${BUILD_DIR}/ireland-${DATE_TAG}-omt.pmtiles"
FINAL_OUT="${TILE_DIR}/ireland-${DATE_TAG}-omt.pmtiles"

mkdir -p "${BUILD_DIR}"

if [ -f "${FINAL_OUT}" ]; then
    echo "Up-to-date: ${FINAL_OUT} already exists, skipping rebuild."
    exit 0
fi

echo "Downloading ${PBF_URL}"
rm -f "${PBF}"
wget --no-verbose -O "${PBF}" "${PBF_URL}"
echo "PBF size: $(stat -c%s "${PBF}") bytes"

echo "Running tilemaker (OpenMapTiles schema) -> ${TMP_OUT}"
rm -f "${TMP_OUT}"
"${TILEMAKER_BIN}" \
    --input "${PBF}" \
    --output "${TMP_OUT}" \
    --config "${TILEMAKER_RES}/config-openmaptiles.json" \
    --process "${TILEMAKER_RES}/process-openmaptiles.lua"

mv -f "${TMP_OUT}" "${FINAL_OUT}"
rm -f "${PBF}"
echo "Wrote ${FINAL_OUT} ($(stat -c%s "${FINAL_OUT}") bytes)"

# Retain the previous .pmtiles bundle (rollback target); prune anything older.
# Sort by date in filename and keep the two newest matching bundles.
mapfile -t bundles < <(ls -1 "${TILE_DIR}"/ireland-*-omt.pmtiles 2>/dev/null | sort -r)
for stale in "${bundles[@]:2}"; do
    echo "Pruning ${stale}"
    rm -f "${stale}"
done
