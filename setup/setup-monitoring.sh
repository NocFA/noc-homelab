#!/usr/bin/env bash
# Linux Homelab Monitoring & Management Setup
#
# Usage: ./setup/setup-monitoring.sh
#
# This script will:
# 1. Install Docker & Docker Compose
# 2. Deploy Arcane (Docker management UI)
# 3. Deploy Gatus (Service health monitoring)
# 4. Install & Configure Glances (System metrics)
# 5. Install & Configure Homelab Agent (Dashboard integration)

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
MAGENTA='\033[1;35m'
NC='\033[0m'

success() { echo -e "${GREEN}$1${NC}"; }
error()   { echo -e "${RED}$1${NC}"; }
info()    { echo -e "${CYAN}$1${NC}"; }
warn()    { echo -e "${YELLOW}$1${NC}"; }

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IP_ADDR=$(hostname -I | awk '{print $1}')

echo ""
echo -e "${MAGENTA}================================================${NC}"
echo -e "${MAGENTA}  Linux Homelab Monitoring Setup                ${NC}"
echo -e "${MAGENTA}================================================${NC}"
echo ""

# === STEP 1: Install Docker ===
echo ""
echo -e "${YELLOW}[1/5] Installing Docker${NC}"
echo "--------------------------------------"

if ! command -v docker &>/dev/null; then
    info "Installing Docker..."
    sudo apt-get update
    sudo apt-get install -y ca-certificates curl gnupg
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    success "Docker installed"
else
    success "Docker already installed: $(docker --version)"
fi

# === STEP 2: Deploy Arcane ===
echo ""
echo -e "${YELLOW}[2/5] Deploying Arcane${NC}"
echo "--------------------------------------"

ARCANE_DIR="$REPO_ROOT/services/arcane"
mkdir -p "$ARCANE_DIR"

if [[ ! -f "$ARCANE_DIR/docker-compose.yml" ]]; then
    info "Setting up Arcane..."
    # Generate secrets
    SECRETS=$(sudo docker run --rm ghcr.io/getarcaneapp/arcane:latest /app/arcane generate secret)
    ENC_KEY=$(echo "$SECRETS" | grep "ENCRYPTION_KEY" | cut -d'=' -f2)
    JWT_SEC=$(echo "$SECRETS" | grep "JWT_SECRET" | cut -d'=' -f2)

    cat > "$ARCANE_DIR/.env" <<EOF
PUID=$(id -u)
PGID=$(id -g)
TZ=Europe/Dublin
APP_URL=http://$IP_ADDR:3552
ENCRYPTION_KEY=$ENC_KEY
JWT_SECRET=$JWT_SEC
EOF

    cat > "$ARCANE_DIR/docker-compose.yml" <<'EOF'
services:
  arcane:
    image: ghcr.io/getarcaneapp/arcane:latest
    container_name: arcane
    ports:
      - "3552:3552"
    volumes:
      - arcane-data:/app/data
      - /home/noc/noc-homelab/services:/home/noc/noc-homelab/services
    environment:
      - DOCKER_HOST=tcp://docker-socket-proxy:2375
      - APP_URL=${APP_URL}
      - PUID=${PUID}
      - PGID=${PGID}
      - TZ=${TZ}
      - ENCRYPTION_KEY=${ENCRYPTION_KEY}
      - JWT_SECRET=${JWT_SECRET}
    depends_on:
      - docker-socket-proxy
    networks:
      - arcane-net
    restart: unless-stopped

  docker-socket-proxy:
    image: tecnativa/docker-socket-proxy
    container_name: arcane-socket-proxy
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    environment:
      - CONTAINERS=1
      - IMAGES=1
      - VOLUMES=1
      - NETWORKS=1
      - INFO=1
      - PING=1
      - BUILD=1
      - EXEC=1
      - AUTH=1
      - SECRETS=1
      - CONFIGS=1
      - POST=1
    networks:
      - arcane-net
    restart: unless-stopped

volumes:
  arcane-data:

networks:
  arcane-net:
EOF
    cd "$ARCANE_DIR" && sudo docker compose up -d
    success "Arcane deployed at http://$IP_ADDR:3552"
else
    success "Arcane already configured"
fi

# === STEP 3: Deploy Gatus ===
echo ""
echo -e "${YELLOW}[3/5] Deploying Gatus${NC}"
echo "--------------------------------------"

GATUS_DIR="$REPO_ROOT/services/gatus"
if [[ -f "$GATUS_DIR/config.yaml" ]]; then
    info "Starting Gatus..."
    cd "$GATUS_DIR" && sudo docker compose up -d
    success "Gatus deployed at http://$IP_ADDR:3001"
else
    warn "Gatus config.yaml missing. Decrypt it first with sops."
fi

# === STEP 4: Install Glances ===
echo ""
echo -e "${YELLOW}[4/5] Configuring Glances${NC}"
echo "--------------------------------------"

if ! command -v glances &>/dev/null; then
    info "Installing Glances..."
    sudo apt-get install -y glances
fi

info "Configuring Glances service (port 61999)..."
sudo sed -i 's|ExecStart=.*|ExecStart=/usr/bin/glances -s -B 0.0.0.0 -p 61999|' /usr/lib/systemd/system/glances.service
sudo systemctl daemon-reload
sudo systemctl enable glances
sudo systemctl restart glances
success "Glances running on port 61999"

# === STEP 5: Install Agent ===
echo ""
echo -e "${YELLOW}[5/5] Configuring Homelab Agent${NC}"
echo "--------------------------------------"

AGENT_DIR="$REPO_ROOT/agent"
info "Installing Agent dependencies..."
sudo apt-get install -y python3-flask python3-yaml

if [[ ! -f "$AGENT_DIR/config.yaml" ]]; then
    info "Creating Agent config..."
    cp "$AGENT_DIR/config.example.yaml" "$AGENT_DIR/config.yaml"
    # Note: Manual update of config.yaml might be needed
fi

info "Installing Agent systemd service..."
cat > homelab-agent.service <<EOF
[Unit]
Description=NOC Homelab Agent
After=network.target docker.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$AGENT_DIR
ExecStart=/usr/bin/python3 agent.py --port 8080 --config config.yaml
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo mv homelab-agent.service /etc/systemd/system/homelab-agent.service
sudo systemctl daemon-reload
sudo systemctl enable homelab-agent.service
sudo systemctl start homelab-agent.service
success "Agent running on port 8080"

echo ""
echo -e "${MAGENTA}================================================${NC}"
echo -e "${MAGENTA}  Monitoring Setup Complete!                    ${NC}"
echo -e "${MAGENTA}================================================${NC}"
echo ""
