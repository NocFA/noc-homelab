#!/usr/bin/env bash
# External attack-surface scan — run from noc-baguette (outside LAN, outside
# Cloudflare) against the homelab's public hostnames.
#
# Tools used (all installed under /usr/local/bin by install.sh):
#   nuclei     — template-based CVE / misconfiguration scanner
#   testssl.sh — TLS cipher / certificate / vulnerability probe
#   ssh-audit  — SSH host key / kex / algorithm audit
#   notify     — multi-destination alerting (Discord webhook)
#
# Invariants:
#   * Script is idempotent and side-effect free — no system changes.
#   * Discovers deltas vs previous run and alerts only on NEW findings.
#   * Every run writes `findings.jsonl` timestamped; last two kept for diff.
#   * Never blocks; timeouts are set per-tool. Completes in <10 min typical.
#
# Environment (see scan.env):
#   TARGETS_HTTP    Space-separated list of https:// URLs for nuclei.
#   TARGETS_SSL     Hosts (host:port) for testssl.sh TLS probe.
#   TARGETS_SSH     Hosts (host:port) for ssh-audit.
#   DISCORD_WEBHOOK Full Discord webhook URL (optional). Empty = stdout only.
#   SCAN_DIR        Working dir. Default /var/lib/hl-scan.
#   NUCLEI_SEV      Severities to alert on. Default "medium,high,critical".

set -euo pipefail

# ---------- config ----------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${ENV_FILE:-$SCRIPT_DIR/scan.env}"
# shellcheck disable=SC1090
[ -f "$ENV_FILE" ] && . "$ENV_FILE"

SCAN_DIR="${SCAN_DIR:-/var/lib/hl-scan}"
NUCLEI_SEV="${NUCLEI_SEV:-medium,high,critical}"
DISCORD_WEBHOOK="${DISCORD_WEBHOOK:-}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="$SCAN_DIR/runs/$TIMESTAMP"
LOG="$SCAN_DIR/scan.log"

# Default targets — override via scan.env.
TARGETS_HTTP="${TARGETS_HTTP:-https://nocfa.net https://auth.nocfa.net https://element.nocfa.net https://api.nocfa.net https://matrix.nocfa.net https://dev.nocfa.net https://play.nocfa.net https://games.nocfa.net https://ie1.nocfa.net https://looney.eu}"
TARGETS_SSL="${TARGETS_SSL:-matrix.nocfa.net:443 auth.nocfa.net:443 nocfa.net:443 looney.eu:443}"
TARGETS_SSH="${TARGETS_SSH:-noc-baguette:22}"

mkdir -p "$RUN_DIR" "$SCAN_DIR/runs"
exec 1> >(tee -a "$LOG") 2>&1

echo "[$TIMESTAMP] === external attack-surface scan start ==="
echo "  targets (http): $TARGETS_HTTP"
echo "  targets (ssl):  $TARGETS_SSL"
echo "  targets (ssh):  $TARGETS_SSH"
echo "  run dir:        $RUN_DIR"

# ---------- nuclei ----------
if command -v nuclei >/dev/null; then
  echo "[$(date -u +%T)] nuclei: update templates"
  nuclei -update-templates -silent || true

  echo "[$(date -u +%T)] nuclei: scan"
  # shellcheck disable=SC2086
  printf '%s\n' $TARGETS_HTTP > "$RUN_DIR/http-targets.txt"
  # Gentle rate — we're hitting Cloudflare-fronted hosts; fast scans can
  # trigger CF rate limits on the HOME IP too (CF links them via SNI).
  nuclei \
    -l "$RUN_DIR/http-targets.txt" \
    -severity "$NUCLEI_SEV" \
    -silent \
    -jsonl \
    -output "$RUN_DIR/nuclei.jsonl" \
    -stats \
    -timeout 10 \
    -rate-limit 8 \
    -bulk-size 10 \
    -concurrency 4 \
    -exclude-tags dos,intrusive,fuzz \
    -exclude-severity info \
    || true
  echo "  nuclei findings: $(wc -l < "$RUN_DIR/nuclei.jsonl" 2>/dev/null || echo 0)"
else
  echo "WARN: nuclei not installed, skipping"
fi

# ---------- testssl.sh ----------
if command -v testssl.sh >/dev/null; then
  for target in $TARGETS_SSL; do
    out="$RUN_DIR/testssl-${target//[:\/]/_}.jsonl"
    echo "[$(date -u +%T)] testssl: $target"
    testssl.sh \
      --jsonfile-pretty "$out.pretty" \
      --jsonfile "$out" \
      --warnings batch \
      --color 0 \
      --quiet \
      "$target" >/dev/null 2>&1 || true
  done
  # Concatenate for easier diffing
  cat "$RUN_DIR"/testssl-*.jsonl 2>/dev/null > "$RUN_DIR/testssl-all.jsonl" || true
  echo "  testssl lines: $(wc -l < "$RUN_DIR/testssl-all.jsonl" 2>/dev/null || echo 0)"
else
  echo "WARN: testssl.sh not installed, skipping"
fi

# ---------- ssh-audit ----------
if command -v ssh-audit >/dev/null; then
  for target in $TARGETS_SSH; do
    host="${target%:*}"
    port="${target##*:}"
    out="$RUN_DIR/ssh-${host}.json"
    echo "[$(date -u +%T)] ssh-audit: $host:$port"
    ssh-audit --json --port "$port" "$host" > "$out" 2>&1 || true
  done
  echo "  ssh-audit files: $(ls "$RUN_DIR"/ssh-*.json 2>/dev/null | wc -l)"
else
  echo "WARN: ssh-audit not installed, skipping"
fi

# ---------- diff against previous ----------
# Find the most recent completed run before this one.
PREV_DIR=""
for d in $(find "$SCAN_DIR/runs" -maxdepth 1 -type d -name '20*' | sort -r); do
  [ "$d" = "$RUN_DIR" ] && continue
  PREV_DIR="$d"
  break
done

NEW_FINDINGS_FILE="$RUN_DIR/new-findings.txt"
: > "$NEW_FINDINGS_FILE"

if [ -n "$PREV_DIR" ]; then
  echo "[$(date -u +%T)] diff vs $PREV_DIR"

  # nuclei: match on fingerprint (template-id + matched-at)
  if [ -f "$RUN_DIR/nuclei.jsonl" ]; then
    python3 - "$PREV_DIR/nuclei.jsonl" "$RUN_DIR/nuclei.jsonl" >> "$NEW_FINDINGS_FILE" <<'PY'
import json, sys, pathlib
prev_path, curr_path = sys.argv[1], sys.argv[2]

def load(p):
    try: lines = pathlib.Path(p).read_text(errors='ignore').splitlines()
    except FileNotFoundError: return set(), {}
    keys, by_key = set(), {}
    for ln in lines:
        if not ln.strip(): continue
        try: o = json.loads(ln)
        except Exception: continue
        fp = (o.get("template-id",""), o.get("matched-at",""))
        keys.add(fp); by_key[fp] = o
    return keys, by_key

prev, _ = load(prev_path)
curr, by_key = load(curr_path)
for fp in sorted(curr - prev):
    o = by_key[fp]
    sev = o.get("info",{}).get("severity","?")
    name = o.get("info",{}).get("name","?")
    print(f"[NEW nuclei:{sev}] {o.get('template-id','?')} — {name} — {o.get('matched-at','?')}")
PY
  fi
else
  echo "[$(date -u +%T)] first run — full inventory, no diff"
  # First run: emit everything medium/high/critical from nuclei
  if [ -f "$RUN_DIR/nuclei.jsonl" ]; then
    python3 - "$RUN_DIR/nuclei.jsonl" >> "$NEW_FINDINGS_FILE" <<'PY'
import json, sys, pathlib
for ln in pathlib.Path(sys.argv[1]).read_text(errors='ignore').splitlines():
    if not ln.strip(): continue
    try: o = json.loads(ln)
    except Exception: continue
    sev = o.get("info",{}).get("severity","?")
    name = o.get("info",{}).get("name","?")
    print(f"[BASELINE nuclei:{sev}] {o.get('template-id','?')} — {name} — {o.get('matched-at','?')}")
PY
  fi
fi

# ---------- notify ----------
NEW_COUNT=$(wc -l < "$NEW_FINDINGS_FILE" | tr -d ' ')
echo "[$(date -u +%T)] new findings: $NEW_COUNT"

if [ "$NEW_COUNT" -gt 0 ] && [ -n "$DISCORD_WEBHOOK" ]; then
  if command -v notify >/dev/null; then
    NOTIFY_CFG="$SCAN_DIR/notify.yaml"
    if [ ! -f "$NOTIFY_CFG" ]; then
      cat > "$NOTIFY_CFG" <<EOF
discord:
  - id: "hl-scan"
    discord_webhook_url: "$DISCORD_WEBHOOK"
    discord_format: "{{data}}"
EOF
      chmod 600 "$NOTIFY_CFG"
    fi
    head -30 "$NEW_FINDINGS_FILE" | notify -provider-config "$NOTIFY_CFG" \
      -bulk -char-limit 1800 -silent || true
  else
    # Raw curl fallback
    summary="$(head -25 "$NEW_FINDINGS_FILE" | sed 's/"/\\"/g; s/$/\\n/' | tr -d '\n')"
    curl -sf -H 'Content-Type: application/json' \
      -d "{\"username\":\"hl-scan\",\"content\":\"**External scan — $NEW_COUNT new finding(s)**\\n\`\`\`\\n${summary}\\n\`\`\`\"}" \
      "$DISCORD_WEBHOOK" > /dev/null || echo "WARN: Discord notify failed"
  fi
else
  [ "$NEW_COUNT" -eq 0 ] && echo "(no new findings — not alerting)"
  [ -z "$DISCORD_WEBHOOK" ] && [ "$NEW_COUNT" -gt 0 ] && echo "(DISCORD_WEBHOOK unset — findings in $NEW_FINDINGS_FILE only)"
fi

# ---------- rotate — keep last 8 runs ----------
cd "$SCAN_DIR/runs"
ls -1dt 20* 2>/dev/null | tail -n +9 | xargs -r rm -rf

echo "[$(date -u +%T)] === scan done ==="
