#!/usr/bin/env python3
"""Single-shot health probe for CrowdSec stack on noc-tux.

Called via SSH from dashboard's SecurityHealthMonitor. Emits one JSON line on
stdout describing the current state of the security stack.

Checks:
    - crowdsec.service active state
    - crowdsec-firewall-bouncer.service active state
    - panic count in bouncer journal over last 10 min (catches Restart=always
      panic-loops where systemd never reports failed)
    - bouncer LAPI last_pull age in seconds (>5 min = auth/network broken)
    - cscli decisions count vs ipset crowdsec-blacklists-1 entry count
      (drift = decisions made but not enforced)

Output: single JSON dict with keys:
    crowdsec_active, bouncer_active, panics, last_pull_age,
    decisions_count, ipset_count
"""
import datetime
import json
import re
import subprocess


def run(cmd, timeout=8):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.returncode
    except Exception:
        return "", 1


out = {}

out["crowdsec_active"] = run(["systemctl", "is-active", "crowdsec.service"])[0]
out["bouncer_active"] = run(["systemctl", "is-active", "crowdsec-firewall-bouncer.service"])[0]

panic_out, _ = run([
    "sudo", "-n", "journalctl", "-u", "crowdsec-firewall-bouncer",
    "--since", "10 min ago", "--no-pager",
])
out["panics"] = len(re.findall(r"panic:|fatal error:", panic_out))

bouncers_json, _ = run(["sudo", "-n", "cscli", "bouncers", "list", "-o", "json"])
last_pull_age = None
try:
    bouncers = json.loads(bouncers_json) if bouncers_json else []
    fb = [b for b in bouncers if "firewall" in (b.get("type") or "")]
    if fb:
        ts = fb[0].get("last_pull", "").rstrip("Z").split(".")[0]
        if ts:
            dt = datetime.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S")
            last_pull_age = int((datetime.datetime.utcnow() - dt).total_seconds())
except Exception:
    pass
out["last_pull_age"] = last_pull_age

decisions_json, _ = run(["sudo", "-n", "cscli", "decisions", "list", "-o", "json"])
try:
    decisions = json.loads(decisions_json) or []
    # Each alert can produce multiple decision rows for the same IP (one per
    # scenario it tripped). Firewall ipset only contains the IP once, so
    # dedupe by value before comparing to ipset count.
    unique_ips = set()
    for alert in decisions:
        for d in (alert.get("decisions") or []):
            v = d.get("value")
            if v:
                unique_ips.add(v)
    out["decisions_count"] = len(unique_ips)
except Exception:
    out["decisions_count"] = None

ipset_out, _ = run(["sudo", "-n", "ipset", "list", "crowdsec-blacklists-1"])
ipset_count = None
for line in ipset_out.splitlines():
    if line.startswith("Number of entries:"):
        try:
            ipset_count = int(line.split(":")[1].strip())
        except Exception:
            pass
        break
out["ipset_count"] = ipset_count

print(json.dumps(out))
