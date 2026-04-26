# CrowdSec — intrusion detection (noc-tux)

Parses logs, matches attack scenarios (SSH brute force, HTTP path probes,
Traefik 4xx bursts, auth abuse) and pushes decisions into the local SQLite
DB. The `crowdsec-firewall-bouncer-iptables` reads those decisions and
enforces them via `iptables` + `ipset` — see "Active enforcement" below.

CAPI (community IP blocklist subscription) is enabled too; ~22k bad-actor
IPs land in `crowdsec-blacklists-0` automatically.

## Graduated ban tiers

`profiles.yaml` escalates ban duration based on `GetDecisionsCount(ip)` —
every prior decision still in the DB counts toward the next tier:

| Prior decisions | Ban duration |
| --- | --- |
| 0 (first offender) | 24h |
| 1+ (returning) | 72h (3 days) |
| 4+ (repeat) | 168h (7 days) |
| 10+ (persistent) | 336h (14 days) |

DB retention is set to 60 days (`config.yaml.local` →
`db_config.flush.max_age: 60d`) so an IP that comes back weeks later still
counts as a repeat offender. Profile order in `profiles.yaml` matters —
most-specific tier first, default last, with `on_success: break` between.

## Install (noc-tux)

```bash
# IMPORTANT: do NOT use Ubuntu's apt crowdsec — 24.04 ships a broken 1.4.6
# with incorrect plugin naming. Use the upstream packagecloud repo:
curl -fsSL https://install.crowdsec.net | sudo sh
sudo apt-get install -y crowdsec   # pulls >=1.7.x from crowdsec/crowdsec
# (verify: apt-cache policy crowdsec → version from packagecloud.io)

# Install recommended collections
sudo cscli collections install \
  crowdsecurity/sshd \
  crowdsecurity/linux \
  crowdsecurity/traefik \
  crowdsecurity/base-http-scenarios \
  crowdsecurity/http-cve

# Copy repo configs into /etc/crowdsec
sudo install -o root -g root -m 0644 \
  /home/noc/noc-homelab/services/crowdsec/acquis.yaml /etc/crowdsec/acquis.yaml
sudo install -o root -g root -m 0644 \
  /home/noc/noc-homelab/services/crowdsec/profiles.yaml /etc/crowdsec/profiles.yaml
sudo install -o root -g root -m 0600 \
  /home/noc/noc-homelab/services/crowdsec/config.yaml.local.example /etc/crowdsec/config.yaml.local
sudo mkdir -p /etc/crowdsec/notifications
sudo cp /home/noc/noc-homelab/services/crowdsec/notifications/http_discord.yaml \
        /etc/crowdsec/notifications/http_discord.yaml

# Install Discord webhook URL from .env
set -a; . /home/noc/noc-homelab/services/crowdsec/.env; set +a
sudo sed -i "s|\${CROWDSEC_DISCORD_WEBHOOK}|${CROWDSEC_DISCORD_WEBHOOK}|g" \
  /etc/crowdsec/notifications/http_discord.yaml

sudo systemctl enable --now crowdsec
sudo systemctl restart crowdsec
```

## Exposing LAPI to Tailscale peers (for remote agents)

LAPI listens on `0.0.0.0:8150` (configured in `config.yaml.local`, copied
from `config.yaml.local.example` at install time — see step above). UFW
restricts inbound to `100.64.0.0/10` so only Tailscale peers can connect.

After install, issue per-machine credentials (run once per remote agent):

```bash
sudo cscli machines add noc-local-mac --auto -f -
sudo cscli machines add noc-claw-mac --auto -f -
```

The output goes straight into the agent's `.env` on the other host —
see `services/crowdsec-agent/README.md` for the agent side.

## Validate

```bash
# Confirm parser chain is healthy
sudo cscli metrics

# See which IPs have active decisions
sudo cscli decisions list

# Subscribe to the live event stream (tail)
sudo journalctl -u crowdsec -f

# Trigger a synthetic alert
sudo cscli decisions add --ip 1.2.3.4 --reason "manual test"
# → should fire Discord webhook within ~1s; delete afterward
sudo cscli decisions delete --ip 1.2.3.4
```

## Active enforcement (bouncer installed Apr 2026)

The firewall bouncer is now installed on noc-tux and actively enforcing
decisions. Install steps if rebuilding:

```bash
# 1) Deploy trusted-source whitelist FIRST (prevents future scenarios from
#    ever banning Tailscale / LAN / home IP / OVH VPS).
sudo install -o root -g root -m 0644 \
  /home/noc/noc-homelab/services/crowdsec/postoverflows/homelab-whitelist.yaml \
  /etc/crowdsec/postoverflows/s01-whitelist/homelab-whitelist.yaml
sudo systemctl reload crowdsec
sudo cscli postoverflows list | grep homelab   # verify: enabled,local

# 2) Sanity-check the decisions DB — anything unexpected in here will be
#    blocked the moment the bouncer starts.
sudo cscli decisions list

# 3) Install the firewall bouncer (auto-registers with LAPI via post-install).
sudo apt-get install -y crowdsec-firewall-bouncer-iptables

# 4) Verify.
sudo cscli bouncers list                                # expect cs-firewall-bouncer-* row
sudo iptables -L CROWDSEC_CHAIN -n --line-numbers       # DROP rules matching the ipsets
sudo ipset list crowdsec-blacklists-0 | head            # CAPI community blocklist (~22k IPs)
sudo ipset list crowdsec-blacklists-1 | head            # local scenario bans
```

Key files:
- `postoverflows/homelab-whitelist.yaml` — our trusted ranges (committed)
- `/etc/crowdsec/bouncers/crowdsec-firewall-bouncer.yaml` — bouncer config
  (auto-generated at install, API key embedded, do not commit)
- `iptables INPUT` chain now starts with `CROWDSEC_CHAIN` — runs BEFORE ufw,
  libvirt, and tailscale chains

**Observed behaviour**: at install time the bouncer consumed the existing
`213.209.159.175` decision (a `.env`-scanner from earlier that evening) plus
~22,680 IPs from the CrowdSec Community API blocklist. UFW and Tailscale
continue to work unchanged.

**Warning**: buggy scenario tuning can kick legit users. If something stops
working after install, first check `ipset test crowdsec-blacklists-0 <ip>`
then either extend `homelab-whitelist.yaml` or
`sudo cscli decisions delete --ip <ip>`.
