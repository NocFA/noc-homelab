# CrowdSec — intrusion detection (noc-tux)

Parses logs, matches attack scenarios (SSH brute force, HTTP path probes,
Traefik 4xx bursts, auth abuse) and records decisions in a local SQLite DB.

**Mode: observation-only by default.** No bouncer is attached, so no traffic
is actually blocked. Every hit produces a Discord alert instead, letting you
review scenario accuracy before switching to active blocking.

CAPI (community IP blocklist subscription) is enabled so the agent pulls
crowd-sourced bad-actor lists; those decisions still sit dormant without a
bouncer.

## Install (noc-tux)

```bash
# Ubuntu apt already has crowdsec:
sudo apt-get install -y crowdsec

# Install recommended collections
sudo cscli collections install \
  crowdsecurity/sshd \
  crowdsecurity/linux \
  crowdsecurity/traefik \
  crowdsecurity/base-http-scenarios \
  crowdsecurity/http-cve

# Copy repo configs into /etc/crowdsec
sudo cp /home/noc/noc-homelab/services/crowdsec/acquis.yaml /etc/crowdsec/acquis.yaml
sudo cp /home/noc/noc-homelab/services/crowdsec/profiles.yaml /etc/crowdsec/profiles.yaml
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

## Going active later

Install one bouncer; start with firewall (iptables):

```bash
sudo apt-get install -y crowdsec-firewall-bouncer-iptables

# The bouncer reads /etc/crowdsec/bouncers/crowdsec-firewall-bouncer.yaml.
# BEFORE enabling, verify `cscli decisions list` doesn't contain any IPs you
# actually want to reach (Tailscale peers, home LAN, CI runners, etc).
# Add an allowlist:
sudo cscli decisions list --ip 100.64.0.0/10  # Tailscale — should be empty

sudo cscli postoverflows install crowdsecurity/whitelists
# Then edit /etc/crowdsec/postoverflows/s01-whitelist/whitelists.yaml to keep
# 100.64.0.0/10, 192.168.0.0/16, etc. from ever being banned.

sudo systemctl enable --now crowdsec-firewall-bouncer
```

**Warning**: once the bouncer is running, buggy scenario tuning can kick
legit users. Always keep the whitelist up to date and prefer `captcha`-style
bouncers at the proxy layer before going to iptables-level blocks on public
services.
