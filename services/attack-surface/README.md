# attack-surface — weekly external scanner

Runs on **noc-baguette** (OVH VPS, outside the LAN and outside Cloudflare) so
it hits the homelab's public endpoints the same way an internet attacker
would. Any NEW finding over the previous run pings Discord.

Why noc-baguette:
- Not on the home network — Cloudflare rate-limiting, geoip, and rathole
  tunnels all look like they do from a real attacker.
- Always on, low resource usage, already hardened (Tailscale + whitelist SSH).
- No impact on any homelab machine.

## What gets scanned

- **nuclei** — JSON template CVE/misconfig scanner, `medium,high,critical`
  severities only, `dos,intrusive` tags excluded.
- **testssl.sh** — TLS cipher / certificate / vulnerability probe, JSON output.
  Targets especially `matrix.nocfa.net` (only direct-A public record, no CF
  shield).
- **ssh-audit** — SSH kex / host-key algorithm audit against noc-baguette's
  own SSH.

Endpoints (edit `scan.env`):

```
TARGETS_HTTP  nocfa.net auth element api matrix dev play games ie1 looney.eu
TARGETS_SSL   matrix:443 auth:443 nocfa:443 looney.eu:443
TARGETS_SSH   noc-baguette:22
```

## Install on noc-baguette

```bash
# As root on noc-baguette:
mkdir -p /opt/hl-scan
cp /path/to/noc-homelab/services/attack-surface/* /opt/hl-scan/ -r
cd /opt/hl-scan
bash install.sh        # fetches nuclei, notify, testssl.sh, ssh-audit

# Fill in the Discord webhook
cp scan.env.example scan.env
vi scan.env            # paste DISCORD_WEBHOOK
chmod 600 scan.env
ln -s /opt/hl-scan/scan.env /etc/hl-scan.env

# Systemd unit + timer
cp systemd/hl-scan.service /etc/systemd/system/
cp systemd/hl-scan.timer   /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now hl-scan.timer

# First run (baseline — posts everything)
systemctl start hl-scan.service
journalctl -u hl-scan.service -f
```

## Output

- `/var/lib/hl-scan/runs/<timestamp>/` — nuclei.jsonl, testssl-*.jsonl,
  ssh-*.json, new-findings.txt
- `/var/lib/hl-scan/scan.log` — human log, append-only
- `/var/lib/hl-scan/notify.yaml` — generated on first notification
- Last 8 runs kept; older rotated out.

## Diff model

- Every run stores its full output.
- `scan.sh` walks the previous run directory and diffs nuclei.jsonl by
  `(template-id, matched-at)` fingerprint. Anything unseen is NEW.
- First run is a "baseline" — all findings reported, tagged `BASELINE`.

## Manual invocation / dry run

```bash
ENV_FILE=/opt/hl-scan/scan.env sudo /opt/hl-scan/scan.sh
```

## Tuning

- `NUCLEI_SEV` defaults `medium,high,critical`; widen to include `low,info`
  for maintenance / hardening reviews.
- `-exclude-tags dos,intrusive` is hard-coded in `scan.sh` — don't remove
  without re-thinking rate limits for the public hostnames.
- Timer fires Sundays 03:15 UTC with up to 30m jitter. Weekly is enough —
  daily is overkill for a small homelab.

## Pairs with

- `services/crowdsec/` — reactive (catches what's hitting us right now)
- `services/loki/` — forensic (full log record for post-incident review)
- `noc-homelab-4hp` — Lynis host-hardening baseline (one-shot, complement)
