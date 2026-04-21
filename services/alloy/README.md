# Alloy — Homelab log shippers

One `.alloy` config per machine. Alloy tails local sources (journald, Docker,
files) and pushes to Loki on noc-tux.

| Machine   | Install                                    | Service       | Config target                    |
|-----------|--------------------------------------------|---------------|----------------------------------|
| noc-tux   | `apt install alloy` (Grafana repo)         | systemd       | `/etc/alloy/config.alloy`        |
| noc-local | `brew install grafana/grafana/alloy`       | brew services | `/opt/homebrew/etc/alloy/config.alloy` |
| noc-claw  | `brew install grafana/grafana/alloy`       | brew services | `/opt/homebrew/etc/alloy/config.alloy` |

## Install — noc-tux

```bash
# One-time: add Grafana apt repo and install
sudo mkdir -p /etc/apt/keyrings
wget -q -O - https://apt.grafana.com/gpg.key | gpg --dearmor | sudo tee /etc/apt/keyrings/grafana.gpg > /dev/null
echo "deb [signed-by=/etc/apt/keyrings/grafana.gpg] https://apt.grafana.com stable main" | sudo tee /etc/apt/sources.list.d/grafana.list
sudo apt-get update
sudo apt-get install -y alloy

# Install repo config (symlink to source of truth)
sudo ln -sfn /home/noc/noc-homelab/services/alloy/noc-tux.alloy /etc/alloy/config.alloy

# Let the alloy service read journal + docker socket
sudo usermod -aG systemd-journal alloy
sudo usermod -aG docker alloy

# Enable + start
sudo systemctl enable --now alloy
sudo systemctl restart alloy  # pick up symlinked config
```

## Install — noc-local / noc-claw

```bash
brew tap grafana/grafana
brew install alloy

# Symlink repo config into the brew etc dir
ln -sfn /Users/noc/noc-homelab/services/alloy/<machine>.alloy /opt/homebrew/etc/alloy/config.alloy

# brew services starts it with the shipped plist
brew services start alloy

# Verify
brew services list | grep alloy
tail -f /opt/homebrew/var/log/alloy.log
```

## Verify end-to-end

```bash
# From any machine with Tailscale, hit Loki
curl -s -G http://noc-tux:3100/loki/api/v1/label | jq .

# Query last 5m of noc-tux journal
curl -sG --data-urlencode 'query={machine="noc-tux", job="journal"}' \
  --data-urlencode 'limit=20' http://noc-tux:3100/loki/api/v1/query_range | jq .
```

## Alloy UI (per machine)

Alloy exposes its own debug UI on `:12345` by default (pipeline status,
component health). Bound to `0.0.0.0` — UFW/pf restricts to Tailscale+LAN.
