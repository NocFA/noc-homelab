#!/bin/bash
# Apply noc-claw pf firewall rules
# Blocks all non-Tailscale inbound traffic
# Run once: bash services/pf/apply-noc-claw.sh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONF="$SCRIPT_DIR/noc-claw.conf"
ANCHOR_PATH="/etc/pf.anchors/noc-claw"
PF_CONF="/etc/pf.conf"

echo "Installing pf anchor for noc-claw..."

# Copy anchor config
sudo cp "$CONF" "$ANCHOR_PATH"

# Add anchor to pf.conf if not already present
if ! grep -q "noc-claw" "$PF_CONF"; then
    sudo tee -a "$PF_CONF" > /dev/null <<'EOF'

# noc-claw: block non-Tailscale inbound
anchor "noc-claw"
load anchor "noc-claw" from "/etc/pf.anchors/noc-claw"
EOF
    echo "Added noc-claw anchor to $PF_CONF"
else
    echo "Anchor already in $PF_CONF"
fi

# Enable pf and load rules
sudo pfctl -ef /etc/pf.conf
echo "pf enabled and noc-claw rules loaded."
echo ""
echo "Verify with: sudo pfctl -s rules"
echo "To reload after changes: sudo pfctl -ef /etc/pf.conf"
