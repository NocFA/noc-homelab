#!/usr/bin/env bash
#
# trivy-scan.sh — Homelab CVE scanner
#
# Runs Trivy against the host (OS packages) and any running Docker images,
# aggregates the findings into a single JSON report at
#   $HOME/.cache/homelab-cve/report.json
# consumed by the dashboard /api/cves/summary endpoint.
#
# Runs on macOS (Homebrew trivy) and Linux (apt trivy). Intentionally visibility-
# only — never patches anything.
#
# Usage:
#   scripts/trivy-scan.sh           # full scan, writes report.json
#   scripts/trivy-scan.sh --quick   # OS-only, skip Docker (faster)
#
set -u

QUICK=0
if [[ "${1:-}" == "--quick" ]]; then
    QUICK=1
fi

REPORT_DIR="$HOME/.cache/homelab-cve"
REPORT_FILE="$REPORT_DIR/report.json"
TMP_DIR="$(mktemp -d -t trivy-scan.XXXXXX)"
trap 'rm -rf "$TMP_DIR"' EXIT

mkdir -p "$REPORT_DIR"

# Find trivy — Homebrew puts it in /opt/homebrew/bin, apt in /usr/bin.
TRIVY=""
for candidate in /opt/homebrew/bin/trivy /usr/local/bin/trivy /usr/bin/trivy; do
    if [[ -x "$candidate" ]]; then
        TRIVY="$candidate"
        break
    fi
done
if [[ -z "$TRIVY" ]] && command -v trivy >/dev/null 2>&1; then
    TRIVY="$(command -v trivy)"
fi
if [[ -z "$TRIVY" ]]; then
    echo "trivy not found in PATH or known locations" >&2
    exit 1
fi

HOSTNAME_SHORT="$(hostname -s 2>/dev/null || hostname)"
OS_KIND="$(uname -s)"
TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Severities we care about. MEDIUM gets included so the dashboard can show
# trend data but alerting should only fire on CRITICAL+HIGH.
SEVERITIES="CRITICAL,HIGH,MEDIUM"

# Targets we'll scan. Each entry: name|kind|arg
TARGETS=()

# ── Filesystem scan ─────────────────────────────────────────────────────────
if [[ "$OS_KIND" == "Linux" ]]; then
    # rootfs scan of / with OS-package scanner. --pkg-types os limits to
    # dpkg/rpm/apk so we avoid the slow language-ecosystem walk of the whole
    # filesystem; that still catches apt CVEs which is what we care about here.
    TARGETS+=("rootfs|rootfs|/")
elif [[ "$OS_KIND" == "Darwin" ]]; then
    # macOS: no OS-package scanner, but gobinary scan of /opt/homebrew/bin
    # catches CVEs in tools we actually care about (rclone, caddy, trivy itself).
    if [[ -d /opt/homebrew/bin ]]; then
        TARGETS+=("homebrew-bin|fs|/opt/homebrew/bin")
    fi
fi

# ── Docker image scan ───────────────────────────────────────────────────────
IMAGES=()
if [[ $QUICK -eq 0 ]] && command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    # dedupe — two containers often share an image
    while IFS= read -r img; do
        [[ -z "$img" ]] && continue
        [[ "$img" == "<none>:<none>" ]] && continue
        IMAGES+=("$img")
    done < <(docker ps --format '{{.Image}}' 2>/dev/null | sort -u)
fi

for img in "${IMAGES[@]+"${IMAGES[@]}"}"; do
    # Use image name as target label; sanitise for filenames.
    label="image-$(echo "$img" | tr '/:@' '___')"
    TARGETS+=("$label|image|$img")
done

# ── Run scans ───────────────────────────────────────────────────────────────
TARGET_JSONS=()
for entry in "${TARGETS[@]+"${TARGETS[@]}"}"; do
    IFS='|' read -r name kind arg <<<"$entry"
    out="$TMP_DIR/$name.json"
    log="$TMP_DIR/$name.log"
    case "$kind" in
        rootfs)
            "$TRIVY" rootfs --quiet --format json --severity "$SEVERITIES" \
                --pkg-types os --scanners vuln --timeout 10m \
                --output "$out" "$arg" >"$log" 2>&1
            ;;
        fs)
            "$TRIVY" fs --quiet --format json --severity "$SEVERITIES" \
                --scanners vuln --timeout 5m \
                --output "$out" "$arg" >"$log" 2>&1
            ;;
        image)
            "$TRIVY" image --quiet --format json --severity "$SEVERITIES" \
                --pkg-types os,library --scanners vuln --timeout 10m \
                --output "$out" "$arg" >"$log" 2>&1
            ;;
    esac
    rc=$?
    if [[ $rc -ne 0 || ! -s "$out" ]]; then
        err_msg="$(tail -5 "$log" 2>/dev/null | tr '\n' ' ' | cut -c1-400)"
        TARGET_JSONS+=("{\"name\":\"$name\",\"kind\":\"$kind\",\"target\":\"$arg\",\"error\":\"$err_msg\",\"counts\":{\"CRITICAL\":0,\"HIGH\":0,\"MEDIUM\":0},\"findings\":[]}")
        continue
    fi

    # Summarise via python rather than jq so we don't need extra deps.
    summary="$(TRIVY_OUT="$out" TARGET_NAME="$name" TARGET_KIND="$kind" TARGET_ARG="$arg" python3 <<'PY'
import json, os
try:
    with open(os.environ["TRIVY_OUT"]) as f:
        doc = json.load(f)
except Exception as e:
    print(json.dumps({
        "name": os.environ["TARGET_NAME"],
        "kind": os.environ["TARGET_KIND"],
        "target": os.environ["TARGET_ARG"],
        "error": f"parse: {e}",
        "counts": {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0},
        "findings": [],
    }))
    raise SystemExit(0)

counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0}
findings = []
for result in doc.get("Results") or []:
    target = result.get("Target", "")
    for v in result.get("Vulnerabilities") or []:
        sev = v.get("Severity", "UNKNOWN")
        if sev in counts:
            counts[sev] += 1
        findings.append({
            "id": v.get("VulnerabilityID", ""),
            "pkg": v.get("PkgName", ""),
            "installed": v.get("InstalledVersion", ""),
            "fixed": v.get("FixedVersion", "") or "",
            "severity": sev,
            "title": (v.get("Title") or "")[:200],
            "target": target,
        })
# Sort by severity (CRITICAL first) then by id
sev_rank = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2}
findings.sort(key=lambda f: (sev_rank.get(f["severity"], 9), f["id"]))

print(json.dumps({
    "name": os.environ["TARGET_NAME"],
    "kind": os.environ["TARGET_KIND"],
    "target": os.environ["TARGET_ARG"],
    "counts": counts,
    "findings": findings[:200],  # cap per target
    "findings_total": len(findings),
}))
PY
    )"
    TARGET_JSONS+=("$summary")
done

# ── Aggregate final report ──────────────────────────────────────────────────
TARGETS_JSON="["
first=1
for j in "${TARGET_JSONS[@]+"${TARGET_JSONS[@]}"}"; do
    if [[ $first -eq 1 ]]; then
        first=0
    else
        TARGETS_JSON+=","
    fi
    TARGETS_JSON+="$j"
done
TARGETS_JSON+="]"

# Totals + top critical/high across targets, produced by python for safety.
FINAL="$(TARGETS_RAW="$TARGETS_JSON" HOST="$HOSTNAME_SHORT" TS="$TIMESTAMP" TRIVY_VER="$("$TRIVY" --version 2>/dev/null | awk '/^Version:/ {print $2; exit}')" python3 <<'PY'
import json, os
targets = json.loads(os.environ["TARGETS_RAW"])
totals = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0}
for t in targets:
    c = t.get("counts") or {}
    for k in totals:
        totals[k] += int(c.get(k, 0) or 0)

# Top critical/high across everything, for the summary pane.
top = []
for t in targets:
    for f in t.get("findings") or []:
        if f.get("severity") in ("CRITICAL", "HIGH"):
            top.append({**f, "source": t.get("name")})
sev_rank = {"CRITICAL": 0, "HIGH": 1}
top.sort(key=lambda f: (sev_rank.get(f["severity"], 9), f.get("id", "")))
top = top[:25]

print(json.dumps({
    "hostname": os.environ["HOST"],
    "timestamp": os.environ["TS"],
    "trivy_version": os.environ.get("TRIVY_VER") or "",
    "totals": totals,
    "targets": targets,
    "top": top,
}, separators=(",", ":")))
PY
)"

echo "$FINAL" >"$REPORT_FILE.tmp" && mv "$REPORT_FILE.tmp" "$REPORT_FILE"

# Also print a one-line summary to stdout for the scheduler log.
SUMMARY="$(REPORT="$REPORT_FILE" python3 <<'PY'
import json, os
with open(os.environ["REPORT"]) as f:
    d = json.load(f)
t = d["totals"]
print(f"critical={t['CRITICAL']} high={t['HIGH']} medium={t['MEDIUM']} targets={len(d['targets'])}")
PY
)"
echo "trivy-scan $HOSTNAME_SHORT: $SUMMARY"

# ── Diff vs previous run + Discord notify on new CRITICAL/HIGH ──────────────
# Pattern matches AIDE FIM (linux/scripts/aide-check.sh): sources
# configs/discord-webhooks.env if present, posts only when there's a delta,
# uses DISCORD_WEBHOOK_LOCKDOWN. First run on a host has no prev report, so
# the bootstrap path skips notify — only deltas after that fire.
PREV_REPORT="$REPORT_DIR/report.prev.json"

# Locate webhook env. Repo root is two-up from scripts/. Don't fail the scan
# on missing env — just skip the notify step.
SCRIPT_DIR_REAL="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR_REAL/.." && pwd)"
WEBHOOK_ENV="$REPO_ROOT/configs/discord-webhooks.env"
if [[ -r "$WEBHOOK_ENV" ]]; then
    # shellcheck source=/dev/null
    source "$WEBHOOK_ENV"
fi

if [[ -n "${DISCORD_WEBHOOK_LOCKDOWN:-}" ]]; then
    NOTIFY_OUT="$(REPORT="$REPORT_FILE" PREV="$PREV_REPORT" WEBHOOK="$DISCORD_WEBHOOK_LOCKDOWN" HOST="$HOSTNAME_SHORT" python3 <<'PY'
import json, os, urllib.request, urllib.error

def load(path):
    with open(path) as f:
        return json.load(f)

cur = load(os.environ["REPORT"])
prev_path = os.environ["PREV"]

def critical_high_set(report):
    out = set()
    for t in report.get("targets") or []:
        for f in t.get("findings") or []:
            if f.get("severity") in ("CRITICAL", "HIGH"):
                # Identity = (CVE id, target_name, package). The same CVE in
                # two different images is two findings worth flagging.
                out.add((f.get("id", ""), t.get("name", ""), f.get("pkg", "")))
    return out

if not os.path.exists(prev_path):
    print("NOTIFY=skip (no prev report, bootstrapping baseline)")
    raise SystemExit(0)

try:
    prev = load(prev_path)
except (json.JSONDecodeError, ValueError) as e:
    print(f"NOTIFY=skip (prev report unreadable: {e})")
    raise SystemExit(0)

prev_set = critical_high_set(prev)
cur_set = critical_high_set(cur)
new_keys = cur_set - prev_set

if not new_keys:
    print("NOTIFY=skip (no new CRITICAL/HIGH findings)")
    raise SystemExit(0)

# Materialise full records for the new keys, preserving current report data.
new_findings = []
for t in cur.get("targets") or []:
    for f in t.get("findings") or []:
        key = (f.get("id", ""), t.get("name", ""), f.get("pkg", ""))
        if key in new_keys and f.get("severity") in ("CRITICAL", "HIGH"):
            new_findings.append({**f, "source": t.get("name", "")})

sev_rank = {"CRITICAL": 0, "HIGH": 1}
new_findings.sort(key=lambda f: (sev_rank.get(f["severity"], 9), f.get("id", "")))

# Build embed body. Cap at 25 lines; Discord limit is 4096 chars per embed
# description, so be conservative.
host = os.environ["HOST"]
n_crit = sum(1 for f in new_findings if f["severity"] == "CRITICAL")
n_high = sum(1 for f in new_findings if f["severity"] == "HIGH")
title = f"Trivy: {len(new_findings)} new finding(s) on {host}"

lines = [f"**{n_crit} critical, {n_high} high** new since last scan.", ""]
for f in new_findings[:25]:
    sev = f["severity"]
    fixed = f.get("fixed") or "no fix"
    lines.append(f"`{sev[:1]}` `{f['id']}` {f['pkg']} {f['installed']} -> {fixed} ({f['source']})")
if len(new_findings) > 25:
    lines.append(f"\n...and {len(new_findings)-25} more.")

body = "\n".join(lines)
if len(body) > 3800:
    body = body[:3800] + "\n...(truncated)"

# Orange for HIGH-only, red if any CRITICAL.
color = 15158332 if n_crit else 16753920
payload = {"embeds": [{
    "title": title,
    "description": body,
    "color": color,
    "footer": {"text": f"Trivy {cur.get('trivy_version','')} - {host}"},
}]}

req = urllib.request.Request(
    os.environ["WEBHOOK"],
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        print(f"NOTIFY=ok ({resp.status}) new={len(new_findings)}")
except urllib.error.HTTPError as e:
    print(f"NOTIFY=fail http={e.code} body={e.read()[:200]!r}")
except Exception as e:
    print(f"NOTIFY=fail err={e}")
PY
)"
    echo "trivy-notify $HOSTNAME_SHORT: $NOTIFY_OUT"
fi

# Rotate current → prev for next run's diff. Always do this, even on
# first-run/skip path, so subsequent runs have a baseline to compare to.
cp "$REPORT_FILE" "$PREV_REPORT"
