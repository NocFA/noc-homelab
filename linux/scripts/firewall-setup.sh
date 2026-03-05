#!/bin/bash
# noc-tux firewall setup
# Blocks external access to non-essential ports while preserving Docker networking
#
# Two-layer approach:
#   1. UFW (INPUT chain) — blocks host-level services from internet
#   2. DOCKER-USER chain — blocks Docker-published ports from internet
#
# Docker port mappings (host→container):
#   80→8080 (Traefik HTTP), 443→8443 (Traefik HTTPS), 8448→8448 (Matrix federation)
#   3478→3478 (coturn STUN), 5349→5349 (coturn STUN TLS)
#   49152-49172→49152-49172 (coturn TURN relay)
#   7891→7891 (LiveKit TCP), 7892→7892 (LiveKit UDP)
#   5350→5350 (LiveKit), 3479→3479 (LiveKit)
#
# DOCKER-USER chain sees post-DNAT packets, so we match on CONTAINER ports
set -euo pipefail

WAN_IF="${WAN_IF:-wlo1}"
LOCAL_NET="${LOCAL_NET:-192.168.1.0/24}"
TAILSCALE_NET="100.64.0.0/10"

echo "=== Setting up safety valve (auto-disable in 5 minutes) ==="
(sleep 300 && sudo ufw disable 2>/dev/null && sudo iptables -F DOCKER-USER 2>/dev/null && sudo iptables -A DOCKER-USER -j RETURN 2>/dev/null && echo "SAFETY: Firewall disabled") &
SAFETY_PID=$!
echo "Safety PID: $SAFETY_PID"

echo ""
echo "=== Phase 1: UFW setup (host services) ==="

sudo ufw --force reset

sudo ufw default deny incoming
sudo ufw default allow outgoing

# SSH from anywhere (CRITICAL)
sudo ufw allow 22/tcp comment "SSH"

# Local network and Tailscale - full access
sudo ufw allow from "$LOCAL_NET" comment "Local network"
sudo ufw allow from $TAILSCALE_NET comment "Tailscale"
sudo ufw allow in on tailscale0 comment "Tailscale interface"

# Docker bridge traffic
sudo ufw allow in on docker0 comment "Docker bridge"

# Tailscale WireGuard
sudo ufw allow 41641/udp comment "Tailscale WireGuard"

sudo ufw --force enable
echo "UFW enabled!"
sudo ufw status

echo ""
echo "=== Phase 2: DOCKER-USER chain ==="

sudo iptables -F DOCKER-USER

# Allow established connections
sudo iptables -A DOCKER-USER -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN

# Allow local network and Tailscale
sudo iptables -A DOCKER-USER -s "$LOCAL_NET" -j RETURN
sudo iptables -A DOCKER-USER -s $TAILSCALE_NET -j RETURN
sudo iptables -A DOCKER-USER -i tailscale0 -j RETURN
sudo iptables -A DOCKER-USER -i lo -j RETURN

# Allow Docker bridge inter-container traffic
sudo iptables -A DOCKER-USER -i br-+ -j RETURN
sudo iptables -A DOCKER-USER -i docker0 -j RETURN

# Internet-accessible Docker ports (container ports, post-DNAT)

# Traefik HTTPS (host:443 → container:8443)
sudo iptables -A DOCKER-USER -i "$WAN_IF" -p tcp --dport 8443 -j RETURN
sudo iptables -A DOCKER-USER -i "$WAN_IF" -p udp --dport 8443 -j RETURN

# Matrix federation (host:8448 → container:8448)
sudo iptables -A DOCKER-USER -i "$WAN_IF" -p tcp --dport 8448 -j RETURN
sudo iptables -A DOCKER-USER -i "$WAN_IF" -p udp --dport 8448 -j RETURN

# TURN/STUN
sudo iptables -A DOCKER-USER -i "$WAN_IF" -p tcp --dport 3478 -j RETURN
sudo iptables -A DOCKER-USER -i "$WAN_IF" -p udp --dport 3478 -j RETURN
sudo iptables -A DOCKER-USER -i "$WAN_IF" -p tcp --dport 5349 -j RETURN
sudo iptables -A DOCKER-USER -i "$WAN_IF" -p udp --dport 5349 -j RETURN

# TURN relay
sudo iptables -A DOCKER-USER -i "$WAN_IF" -p udp --dport 49152:49172 -j RETURN

# LiveKit
sudo iptables -A DOCKER-USER -i "$WAN_IF" -p tcp --dport 7891 -j RETURN
sudo iptables -A DOCKER-USER -i "$WAN_IF" -p udp --dport 7892 -j RETURN
sudo iptables -A DOCKER-USER -i "$WAN_IF" -p tcp --dport 5350 -j RETURN
sudo iptables -A DOCKER-USER -i "$WAN_IF" -p udp --dport 3479 -j RETURN

# DROP everything else from WAN to Docker containers
sudo iptables -A DOCKER-USER -i "$WAN_IF" -j DROP

# Allow everything else (other interfaces)
sudo iptables -A DOCKER-USER -j RETURN

echo ""
echo "DOCKER-USER rules:"
sudo iptables -L DOCKER-USER -n -v --line-numbers

echo ""
echo "=== Cancelling safety valve ==="
kill $SAFETY_PID 2>/dev/null && echo "Safety valve cancelled." || echo "Safety valve already gone."

echo ""
echo "=== Making rules persistent ==="
sudo mkdir -p /etc/iptables
sudo iptables-save | grep -E '(DOCKER-USER|^[*:]|COMMIT)' | sudo tee /etc/iptables/docker-user.rules > /dev/null

cat << 'UNIT' | sudo tee /etc/systemd/system/docker-user-firewall.service > /dev/null
[Unit]
Description=Restore DOCKER-USER iptables rules
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
ExecStart=/bin/bash -c 'iptables -F DOCKER-USER; grep -E "^-A DOCKER-USER" /etc/iptables/docker-user.rules | while read line; do iptables $line; done'
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable docker-user-firewall.service

echo ""
echo "=== Done! ==="
