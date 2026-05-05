#!/usr/bin/env bash
# Mirror OpenFreeMap's style/sprite/font/raster assets to /home/webdev/tiles/
# so tiles.looney.eu can serve a stand-alone copy of OFM's reference styles
# without any external requests to tiles.openfreemap.org.
#
# Re-run after each PMTiles refresh — the styles are rewritten to point at
# the current planet PMTiles filename. Idempotent.
#
# Args: $1 = current planet pmtiles filename, e.g. "planet-2026-04-29.pmtiles".
set -euo pipefail

PMTILES_FILE="${1:?usage: $0 planet-YYYY-MM-DD.pmtiles}"
TILE_DIR="/home/webdev/tiles"
OFM_BASE="https://tiles.openfreemap.org"
OUR_BASE="https://tiles.looney.eu"

cd "${TILE_DIR}"
mkdir -p sprites/ofm_f384 fonts natural_earth/ne2sr styles

echo "== Mirror sprites =="
for variant in 'ofm' 'ofm@2x'; do
    for ext in json png; do
        curl -sfL -o "sprites/ofm_f384/${variant}.${ext}" \
            "${OFM_BASE}/sprites/ofm_f384/${variant}.${ext}"
    done
done
echo "  sprites: $(find sprites -type f | wc -l) files"

echo "== Mirror fonts (Noto Sans Bold/Italic/Regular x 256 ranges) =="
for stack in 'Noto Sans Bold' 'Noto Sans Italic' 'Noto Sans Regular'; do
    mkdir -p "fonts/${stack}"
done
fetch_font() {
    local stack="$1" idx="$2"
    local encoded="${stack// /%20}"
    local start=$((idx*256))
    local end=$((start+255))
    local out="fonts/${stack}/${start}-${end}.pbf"
    local code
    code=$(curl -sL -o "${out}.tmp" -w '%{http_code}' \
        "${OFM_BASE}/fonts/${encoded}/${start}-${end}.pbf")
    if [ "${code}" = "200" ]; then
        mv -f "${out}.tmp" "${out}"
    else
        rm -f "${out}.tmp" "${out}"
    fi
}
export -f fetch_font
export OFM_BASE
for stack in 'Noto Sans Bold' 'Noto Sans Italic' 'Noto Sans Regular'; do
    seq 0 255 | xargs -I{} -P 16 bash -c 'fetch_font "$0" "$1"' "${stack}" "{}"
done
echo "  fonts: $(find fonts -name '*.pbf' | wc -l) pbfs"

echo "== Mirror Natural Earth raster z0-z6 =="
for z in 0 1 2 3 4 5 6; do
    n=$((1<<z))
    for x in $(seq 0 $((n-1))); do
        mkdir -p "natural_earth/ne2sr/${z}/${x}"
    done
done
fetch_tile() {
    local p="$1"
    curl -sfL -o "natural_earth/ne2sr/${p}.png" \
        "${OFM_BASE}/natural_earth/ne2sr/${p}.png" || true
}
export -f fetch_tile
python3 -c "
for z in range(7):
    n = 1<<z
    for x in range(n):
        for y in range(n):
            print(f'{z}/{x}/{y}')
" | xargs -I{} -P 32 bash -c 'fetch_tile "$0"' {}
echo "  raster: $(find natural_earth -name '*.png' | wc -l) tiles"

echo "== Mirror + rewrite styles =="
for s in liberty bright positron; do
    raw="$(curl -sfL "${OFM_BASE}/styles/${s}")"
    # Rewrite all OFM URLs to our domain. The vector source uses a TileJSON
    # URL pointing at /planet — replace that whole `url:` value with a
    # pmtiles:// URL pointing at our PMTiles archive (requires the maplibre
    # pmtiles protocol handler client-side, which lovelang already wires up).
    rewritten="$(printf '%s' "${raw}" \
        | sed "s|${OFM_BASE}/sprites|${OUR_BASE}/sprites|g" \
        | sed "s|${OFM_BASE}/fonts|${OUR_BASE}/fonts|g" \
        | sed "s|${OFM_BASE}/natural_earth|${OUR_BASE}/natural_earth|g" \
        | sed "s|\"${OFM_BASE}/planet\"|\"pmtiles://${OUR_BASE}/${PMTILES_FILE}\"|g")"
    printf '%s' "${rewritten}" > "styles/${s}"
    echo "  styles/${s}: $(printf '%s' "${rewritten}" | wc -c) bytes"
done

echo "== Disk usage =="
du -sh sprites fonts natural_earth styles
echo "== Done =="
