#!/usr/bin/env bash
# Mirror the latest OpenFreeMap weekly planet build to a self-hosted PMTiles file.
#
# OpenFreeMap publishes Btrfs + MBTiles weekly snapshots at
#   https://btrfs.openfreemap.com/areas/planet/<YYYYMMDD_HHMMSS>_pt/tiles.mbtiles
# but explicitly does NOT ship PMTiles (range-cost concern at their CDN scale).
# We pull the MBTiles, verify SHA256, convert locally with go-pmtiles, and serve
# the resulting PMTiles file from /home/webdev/tiles/.
#
# Output: /home/webdev/tiles/planet-YYYY-MM-DD.pmtiles  (date = OFM build date,
# so the filename reflects the data vintage and stays immutable-cache-safe).
#
# Run as User=webdev via pmtiles-rebuild.service.
set -euo pipefail

TILE_DIR="/home/webdev/tiles"
BUILD_DIR="${TILE_DIR}/build"
PMTILES_BIN="/usr/local/bin/go-pmtiles"
INDEX_URL="https://btrfs.openfreemap.com/files.txt"
BASE_URL="https://btrfs.openfreemap.com"

mkdir -p "${BUILD_DIR}"

echo "Resolving latest OpenFreeMap planet build from ${INDEX_URL}"
LATEST_DIR="$(curl -fsSL "${INDEX_URL}" \
    | grep -E '^areas/planet/[0-9]{8}_[0-9]{6}_pt/tiles\.mbtiles$' \
    | sed -E 's|^areas/planet/([0-9]{8}_[0-9]{6}_pt)/tiles\.mbtiles$|\1|' \
    | sort -r \
    | head -n1)"
if [ -z "${LATEST_DIR}" ]; then
    echo "ERROR: could not find any planet/.../tiles.mbtiles entry in ${INDEX_URL}" >&2
    exit 1
fi
DATE_RAW="${LATEST_DIR%%_*}"                     # 20260429
DATE_TAG="${DATE_RAW:0:4}-${DATE_RAW:4:2}-${DATE_RAW:6:2}"  # 2026-04-29
echo "Latest planet build: ${LATEST_DIR}  (data vintage ${DATE_TAG})"

FINAL_OUT="${TILE_DIR}/planet-${DATE_TAG}.pmtiles"
TMP_PMTILES="${BUILD_DIR}/planet-${DATE_TAG}.pmtiles"
MBTILES="${BUILD_DIR}/tiles.mbtiles"
SUMS="${BUILD_DIR}/SHA256SUMS"

if [ -f "${FINAL_OUT}" ]; then
    echo "Up-to-date: ${FINAL_OUT} already exists, skipping rebuild."
    exit 0
fi

echo "Downloading SHA256SUMS"
curl -fsSL -o "${SUMS}" "${BASE_URL}/areas/planet/${LATEST_DIR}/SHA256SUMS"

echo "Downloading tiles.mbtiles (this is ~94 GB; resumes via --continue if interrupted)"
wget --tries=3 --continue --no-verbose --show-progress \
    -O "${MBTILES}" \
    "${BASE_URL}/areas/planet/${LATEST_DIR}/tiles.mbtiles"

echo "Verifying SHA256"
EXPECTED_SHA="$(awk '$2=="tiles.mbtiles"{print $1}' "${SUMS}")"
if [ -z "${EXPECTED_SHA}" ]; then
    echo "ERROR: tiles.mbtiles missing from SHA256SUMS" >&2
    exit 1
fi
ACTUAL_SHA="$(sha256sum "${MBTILES}" | awk '{print $1}')"
if [ "${EXPECTED_SHA}" != "${ACTUAL_SHA}" ]; then
    echo "ERROR: SHA256 mismatch (expected ${EXPECTED_SHA}, got ${ACTUAL_SHA})" >&2
    exit 1
fi
echo "SHA256 OK: ${ACTUAL_SHA}"

echo "Converting MBTiles -> PMTiles -> ${TMP_PMTILES}"
rm -f "${TMP_PMTILES}"
"${PMTILES_BIN}" convert "${MBTILES}" "${TMP_PMTILES}"

echo "Verifying PMTiles spec v3 magic"
MAGIC="$(head -c 8 "${TMP_PMTILES}" | xxd -p)"
if [ "${MAGIC}" != "504d54696c657303" ]; then
    echo "ERROR: bad PMTiles magic '${MAGIC}' (expected 504d54696c657303)" >&2
    exit 1
fi
echo "Magic OK: ${MAGIC}"

mv -f "${TMP_PMTILES}" "${FINAL_OUT}"
echo "Wrote ${FINAL_OUT} ($(stat -c%s "${FINAL_OUT}") bytes)"

echo "Cleaning up build artifacts"
rm -f "${MBTILES}" "${SUMS}"

# Retain the previous .pmtiles bundle (rollback target); prune anything older.
# Sort by date in filename and keep the two newest matching bundles.
mapfile -t bundles < <(ls -1 "${TILE_DIR}"/planet-*.pmtiles 2>/dev/null | sort -r)
for stale in "${bundles[@]:2}"; do
    echo "Pruning ${stale}"
    rm -f "${stale}"
done

echo "Done."
