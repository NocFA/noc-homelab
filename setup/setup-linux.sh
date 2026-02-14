#!/usr/bin/env bash
# Linux Homelab Setup Script (noc-tux)
# One-command deployment for Real-Debrid media automation pipeline
#
# Usage: ./setup/setup-linux.sh
#
# This script will:
# 1. Create directory structure
# 2. Check prerequisites (zurg, rclone, filebot, java, sops, age)
# 3. Verify SOPS decryption works
# 4. Enable user_allow_other in /etc/fuse.conf
# 5. Create /mnt/zurg mount point
# 6. Set up rclone config (zurg WebDAV remote)
# 7. Install + enable systemd user services
# 8. Start services
#
# No API key prompts -- everything is in sops-encrypted configs

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'

success() { echo -e "${GREEN}$1${NC}"; }
error()   { echo -e "${RED}$1${NC}"; }
info()    { echo -e "${CYAN}$1${NC}"; }
warn()    { echo -e "${YELLOW}$1${NC}"; }

# Detect repo root (script lives in setup/)
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BEADS_ROOT="$REPO_ROOT/../noc-homelab-beads"
AGE_KEY="$BEADS_ROOT/homelab.agekey"

export SOPS_AGE_KEY_FILE="$AGE_KEY"

echo ""
echo -e "${MAGENTA}================================================${NC}"
echo -e "${MAGENTA}  Linux Homelab Setup - Real-Debrid Pipeline    ${NC}"
echo -e "${MAGENTA}================================================${NC}"
echo ""

info "Repo root: $REPO_ROOT"

# === STEP 1: Create Directory Structure ===
echo ""
echo -e "${YELLOW}[1/8] Creating Directory Structure${NC}"
echo "--------------------------------------"

dirs=(
    "$REPO_ROOT/media/movies"
    "$REPO_ROOT/media/shows"
    "$REPO_ROOT/linux/logs"
    "$REPO_ROOT/linux/cache"
    "$REPO_ROOT/linux/services/zurg/data"
)

for dir in "${dirs[@]}"; do
    if [[ ! -d "$dir" ]]; then
        mkdir -p "$dir"
        info "  Created: $dir"
    else
        info "  Exists: $dir"
    fi
done

success "Directory structure created"

# === STEP 2: Check Prerequisites ===
echo ""
echo -e "${YELLOW}[2/8] Checking Prerequisites${NC}"
echo "--------------------------------------"

missing=0

# Zurg binary
ZURG_BIN="$REPO_ROOT/linux/services/zurg/zurg"
if [[ -x "$ZURG_BIN" ]]; then
    success "  Zurg binary found"
else
    warn "  Zurg binary not found at $ZURG_BIN"
    info "    Download from: https://github.com/debridmediamanager/zurg-testing/releases"
    info "    Place at: $ZURG_BIN && chmod +x $ZURG_BIN"
    ((missing++)) || true
fi

# Rclone
if command -v rclone &>/dev/null; then
    success "  rclone found: $(rclone version --check 2>/dev/null | head -1 || rclone --version | head -1)"
else
    warn "  rclone not found"
    info "    Install: sudo apt install rclone  (or https://rclone.org/install/)"
    ((missing++)) || true
fi

# FileBot
if command -v filebot &>/dev/null; then
    success "  FileBot found: $(filebot -version 2>&1 | head -1)"
else
    warn "  FileBot not found"
    info "    Install from: https://www.filebot.net/"
    info "    Requires Java 17+ and a license key"
    ((missing++)) || true
fi

# Java
if command -v java &>/dev/null; then
    success "  Java found: $(java -version 2>&1 | head -1)"
else
    warn "  Java not found"
    info "    Install: sudo apt install openjdk-17-jre"
    ((missing++)) || true
fi

# SOPS
if command -v sops &>/dev/null; then
    success "  sops found: $(sops --version 2>&1)"
else
    warn "  sops not found"
    info "    Install: sudo apt install sops  (or https://github.com/getsops/sops/releases)"
    ((missing++)) || true
fi

# Age key
if [[ -f "$AGE_KEY" ]]; then
    success "  Age key found: $AGE_KEY"
else
    error "  Age key NOT found at $AGE_KEY"
    info "    This is required for decrypting all configs"
    ((missing++)) || true
fi

if [[ $missing -gt 0 ]]; then
    warn "$missing prerequisite(s) missing. Install them and re-run this script."
    echo ""
    read -rp "Continue anyway? (y/n) " reply
    if [[ "$reply" != "y" ]]; then
        exit 1
    fi
fi

# === STEP 3: Verify SOPS Decryption ===
echo ""
echo -e "${YELLOW}[3/8] Verifying SOPS Decryption${NC}"
echo "--------------------------------------"

if command -v sops &>/dev/null && [[ -f "$AGE_KEY" ]]; then
    if sops -d "$REPO_ROOT/configs/media-keys.yaml" >/dev/null 2>&1; then
        success "  SOPS decryption works (media-keys.yaml)"
    else
        error "  SOPS decryption FAILED for media-keys.yaml"
        info "    Check that $AGE_KEY is the correct key"
        exit 1
    fi

    # Check if linux zurg config is encrypted
    if grep -q "^token: YOUR_REAL_DEBRID_API_TOKEN_HERE" "$REPO_ROOT/linux/services/zurg/config.yml" 2>/dev/null; then
        warn "  Zurg config still has placeholder token!"
        info "    1. Edit linux/services/zurg/config.yml and set your Real-Debrid token"
        info "    2. Encrypt: sops -e -i linux/services/zurg/config.yml"
    elif grep -q "^token: ENC\[" "$REPO_ROOT/linux/services/zurg/config.yml" 2>/dev/null; then
        if sops -d "$REPO_ROOT/linux/services/zurg/config.yml" >/dev/null 2>&1; then
            success "  Zurg config is encrypted and decrypts OK"
        else
            error "  Zurg config is encrypted but decryption FAILED"
            exit 1
        fi
    else
        info "  Zurg config has a plaintext token (encrypt before committing!)"
        info "    Run: sops -e -i linux/services/zurg/config.yml"
    fi
else
    warn "  Skipping SOPS verification (sops or age key not available)"
fi

# === STEP 4: Enable user_allow_other in /etc/fuse.conf ===
echo ""
echo -e "${YELLOW}[4/8] Configuring FUSE${NC}"
echo "--------------------------------------"

if grep -q "^user_allow_other" /etc/fuse.conf 2>/dev/null; then
    success "  user_allow_other already enabled in /etc/fuse.conf"
else
    info "  Enabling user_allow_other in /etc/fuse.conf (requires sudo)"
    if sudo sed -i 's/^#user_allow_other/user_allow_other/' /etc/fuse.conf 2>/dev/null; then
        # Check if it worked (might not have been commented, might not exist)
        if ! grep -q "^user_allow_other" /etc/fuse.conf 2>/dev/null; then
            echo "user_allow_other" | sudo tee -a /etc/fuse.conf >/dev/null
        fi
        success "  user_allow_other enabled"
    else
        warn "  Could not modify /etc/fuse.conf"
        info "    Manually add 'user_allow_other' to /etc/fuse.conf"
    fi
fi

# === STEP 5: Create Mount Point ===
echo ""
echo -e "${YELLOW}[5/8] Creating Mount Point${NC}"
echo "--------------------------------------"

if [[ -d /mnt/zurg ]]; then
    success "  /mnt/zurg already exists"
else
    info "  Creating /mnt/zurg (requires sudo)"
    sudo mkdir -p /mnt/zurg
    sudo chown "$USER:$USER" /mnt/zurg
    success "  /mnt/zurg created"
fi

# === STEP 6: Set Up Rclone Config ===
echo ""
echo -e "${YELLOW}[6/8] Setting Up Rclone Config${NC}"
echo "--------------------------------------"

RCLONE_CONF="$HOME/.config/rclone/rclone.conf"
mkdir -p "$(dirname "$RCLONE_CONF")"

if [[ -f "$RCLONE_CONF" ]] && grep -q "\[zurg\]" "$RCLONE_CONF" 2>/dev/null; then
    success "  Rclone [zurg] remote already configured"
else
    info "  Adding [zurg] remote to rclone config"
    cat >> "$RCLONE_CONF" <<'EOF'

[zurg]
type = webdav
url = http://localhost:9999/dav
vendor = other
EOF
    success "  Rclone [zurg] remote added to $RCLONE_CONF"
fi

# === STEP 7: Install Systemd User Services ===
echo ""
echo -e "${YELLOW}[7/8] Installing Systemd User Services${NC}"
echo "--------------------------------------"

SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
mkdir -p "$SYSTEMD_USER_DIR"

for unit in zurg.service rclone-zurg.service; do
    src="$REPO_ROOT/linux/systemd/$unit"
    dest="$SYSTEMD_USER_DIR/$unit"
    if [[ -f "$src" ]]; then
        ln -sf "$src" "$dest"
        info "  Linked: $unit"
    else
        error "  Missing: $src"
    fi
done

systemctl --user daemon-reload
success "  Systemd user services installed and reloaded"

# Enable services (start on login)
systemctl --user enable zurg.service rclone-zurg.service 2>/dev/null || true
success "  Services enabled (will start on login)"

# Enable lingering so user services run without active login
if ! loginctl show-user "$USER" 2>/dev/null | grep -q "Linger=yes"; then
    info "  Enabling loginctl linger (services persist after logout)"
    sudo loginctl enable-linger "$USER"
fi

# === STEP 8: Start Services ===
echo ""
echo -e "${YELLOW}[8/8] Starting Services${NC}"
echo "--------------------------------------"

if [[ -x "$ZURG_BIN" ]]; then
    info "  Starting Zurg..."
    systemctl --user start zurg.service || warn "  Failed to start Zurg (check: systemctl --user status zurg)"
    sleep 3
    if systemctl --user is-active --quiet zurg.service; then
        success "  Zurg is running"
    else
        warn "  Zurg may not have started -- check logs: journalctl --user -u zurg -f"
    fi

    info "  Starting Rclone mount..."
    systemctl --user start rclone-zurg.service || warn "  Failed to start rclone-zurg (check: systemctl --user status rclone-zurg)"
    sleep 3
    if mountpoint -q /mnt/zurg 2>/dev/null; then
        success "  /mnt/zurg is mounted"
    else
        warn "  /mnt/zurg not mounted yet -- check logs: journalctl --user -u rclone-zurg -f"
    fi
else
    warn "  Skipping service start (Zurg binary not found)"
fi

# === SUMMARY ===
echo ""
echo -e "${MAGENTA}================================================${NC}"
echo -e "${MAGENTA}  Setup Complete!                               ${NC}"
echo -e "${MAGENTA}================================================${NC}"
echo ""

success "Next steps:"
info "  1. If Zurg config token is still a placeholder:"
info "     - Edit linux/services/zurg/config.yml with your Real-Debrid token"
info "     - Encrypt: sops -e -i linux/services/zurg/config.yml"
info "     - Restart: systemctl --user restart zurg"
echo ""
info "  2. Verify mount shows content (wait 10-60 seconds):"
info "     ls /mnt/zurg/movies"
info "     ls /mnt/zurg/shows"
echo ""
info "  3. Test FileBot organization:"
info "     ./linux/scripts/filebot-symlinks.sh"
echo ""
info "  4. Configure Emby/Jellyfin libraries:"
info "     Point libraries to: $REPO_ROOT/media/movies"
info "                         $REPO_ROOT/media/shows"
echo ""
info "  5. Monitor logs:"
info "     journalctl --user -u zurg -f"
info "     journalctl --user -u rclone-zurg -f"
info "     tail -f $REPO_ROOT/linux/logs/library-update.log"
echo ""

success "Useful commands:"
info "  Start:    systemctl --user start zurg rclone-zurg"
info "  Stop:     systemctl --user stop rclone-zurg zurg"
info "  Restart:  systemctl --user restart zurg rclone-zurg"
info "  Status:   systemctl --user status zurg rclone-zurg"
info "  Logs:     journalctl --user -u zurg -f"
echo ""
