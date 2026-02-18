#!/usr/bin/env bash
# Linux Homelab Setup Script (noc-tux)
# One-command deployment: git framework + media pipeline
#
# Usage: ./setup/setup-linux.sh
#
# This script will:
# 1.  Create directory structure
# 2.  Check prerequisites
# 3.  Set up noc-homelab-beads repo (age key + memory sync)
# 4.  Install git hooks (SOPS encrypt-on-commit, decrypt-on-pull)
# 5.  Set up GPG commit signing
# 6.  Configure git remotes (origin=GitHub, codeberg=Codeberg)
# 7.  Install + enable git-autopull systemd timer (Codeberg, every 5min)
# 8.  Verify SOPS decryption
# 9.  Configure FUSE
# 10. Create /mnt/zurg mount point
# 11. Set up rclone config
# 12. Install + enable media pipeline systemd services
# 13. Start services
# 14. Link Claude Code memory to beads repo
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
echo -e "${MAGENTA}╔═══════════════════════════════════════════════╗${NC}"
echo -e "${MAGENTA}║   Linux Homelab Setup — noc-tux               ║${NC}"
echo -e "${MAGENTA}╚═══════════════════════════════════════════════╝${NC}"
echo ""

info "Repo root: $REPO_ROOT"

# === STEP 1: Create Directory Structure ===
echo ""
echo -e "${YELLOW}[1/14] Creating Directory Structure${NC}"
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
echo -e "${YELLOW}[2/14] Checking Prerequisites${NC}"
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

# === STEP 3: noc-homelab-beads repo ===
echo ""
echo -e "${YELLOW}[3/14] Setting Up Beads Sync Repo${NC}"
echo "--------------------------------------"

if [[ -d "$BEADS_ROOT/.git" ]]; then
    success "noc-homelab-beads already a git repo"
    git -C "$BEADS_ROOT" pull origin main -q 2>/dev/null && info "  Pulled latest" || true
else
    info "Initializing noc-homelab-beads as git repo..."
    if [[ -f "$AGE_KEY" ]]; then
        AGE_KEY_BACKUP=$(cat "$AGE_KEY")
    fi
    git -C "$BEADS_ROOT" init -b main -q
    git -C "$BEADS_ROOT" remote add origin https://github.com/NocFA/noc-homelab-beads.git
    git -C "$BEADS_ROOT" fetch origin main -q
    git -C "$BEADS_ROOT" reset --hard origin/main -q
    if [[ -n "${AGE_KEY_BACKUP:-}" ]] && [[ ! -f "$AGE_KEY" ]]; then
        echo "$AGE_KEY_BACKUP" > "$AGE_KEY"
        chmod 600 "$AGE_KEY"
    fi
    success "noc-homelab-beads initialized"
fi

if [[ -f "$AGE_KEY" ]]; then
    success "Age key present: $AGE_KEY"
else
    error "Age key missing at $AGE_KEY — copy homelab.agekey before continuing"
    exit 1
fi

# === STEP 4: Git hooks ===
echo ""
echo -e "${YELLOW}[4/14] Installing Git Hooks (SOPS + Beads)${NC}"
echo "--------------------------------------"

HOOKS_DIR="$REPO_ROOT/.git/hooks"

backup_hook() {
    local h="$HOOKS_DIR/$1"
    if [[ -f "$h" ]] && ! grep -q "SOPS auto-encrypt\|SOPS auto-decrypt" "$h" 2>/dev/null; then
        cp "$h" "$h.backup" && info "  Backed up $1 → $1.backup"
    fi
}

backup_hook "pre-commit"
cat > "$HOOKS_DIR/pre-commit" << 'HOOK'
#!/usr/bin/env sh
# Pre-commit hook: SOPS auto-encrypt + beads sync

REPO_ROOT="$(git rev-parse --show-toplevel)"
SOPS_AGE_KEY_FILE="$REPO_ROOT/noc-homelab-beads/homelab.agekey"
SOPS="$(command -v sops 2>/dev/null || echo /usr/local/bin/sops)"

staged=$(git diff --cached --name-only --diff-filter=ACM 2>/dev/null)
[ -z "$staged" ] && exec bd hook pre-commit "$@"

encrypted=0
for file in $staged; do
    encrypt=false
    case "$file" in
        *.env|*.env.*) encrypt=true ;;
        configs/*) encrypt=true ;;
        linux/services/*/config.*|services/*/config.*|services/*/config/*) encrypt=true ;;
        services/*/vars*.yml|services/*/vars*.yaml) encrypt=true ;;
    esac

    if [ "$encrypt" = true ]; then
        full_path="$REPO_ROOT/$file"
        [ -f "$full_path" ] || continue
        if grep -q 'ENC\[AES256_GCM,' "$full_path" 2>/dev/null; then
            continue
        fi
        echo "SOPS auto-encrypt: $file"
        if SOPS_AGE_KEY_FILE="$SOPS_AGE_KEY_FILE" "$SOPS" -e -i "$full_path" 2>/dev/null; then
            git add "$full_path"
            SOPS_AGE_KEY_FILE="$SOPS_AGE_KEY_FILE" "$SOPS" -d -i "$full_path" 2>/dev/null
            encrypted=$((encrypted + 1))
        else
            echo "ERROR: Failed to encrypt $file — aborting commit" >&2
            exit 1
        fi
    fi
done

[ $encrypted -gt 0 ] && echo "SOPS: auto-encrypted $encrypted file(s)"
if command -v bd >/dev/null 2>&1; then exec bd hook pre-commit "$@"; fi
HOOK
chmod +x "$HOOKS_DIR/pre-commit"

backup_hook "post-merge"
cat > "$HOOKS_DIR/post-merge" << 'HOOK'
#!/usr/bin/env sh
# Post-merge hook: SOPS auto-decrypt + beads sync

REPO_ROOT="$(git rev-parse --show-toplevel)"
SOPS_AGE_KEY_FILE="$REPO_ROOT/noc-homelab-beads/homelab.agekey"
SOPS="$(command -v sops 2>/dev/null || echo /usr/local/bin/sops)"

if [ -f "$SOPS_AGE_KEY_FILE" ] && [ -x "$SOPS" ]; then
    changed=$(git diff-tree -r --name-only --no-commit-id ORIG_HEAD HEAD 2>/dev/null)
    decrypted=0
    for file in $changed; do
        decrypt=false
        case "$file" in
            *.env|*.env.*) decrypt=true ;;
            configs/*) decrypt=true ;;
            linux/services/*/config.*|services/*/config.*|services/*/config/*) decrypt=true ;;
            services/*/vars*.yml|services/*/vars*.yaml) decrypt=true ;;
        esac
        if [ "$decrypt" = true ]; then
            full_path="$REPO_ROOT/$file"
            [ -f "$full_path" ] || continue
            if grep -q 'ENC\[AES256_GCM,' "$full_path" 2>/dev/null; then
                SOPS_AGE_KEY_FILE="$SOPS_AGE_KEY_FILE" "$SOPS" -d -i "$full_path" 2>/dev/null && decrypted=$((decrypted + 1))
            fi
        fi
    done
    [ $decrypted -gt 0 ] && echo "SOPS: auto-decrypted $decrypted file(s)"
fi

if command -v bd >/dev/null 2>&1; then exec bd hook post-merge "$@"; fi
HOOK
chmod +x "$HOOKS_DIR/post-merge"

if [[ ! -f "$HOOKS_DIR/pre-push" ]] || ! grep -q "bd hook" "$HOOKS_DIR/pre-push" 2>/dev/null; then
    cat > "$HOOKS_DIR/pre-push" << 'HOOK'
#!/usr/bin/env sh
if command -v bd >/dev/null 2>&1; then exec bd hook pre-push "$@"; fi
HOOK
    chmod +x "$HOOKS_DIR/pre-push"
fi

success "Git hooks installed (pre-commit, post-merge, pre-push)"

# === STEP 5: GPG commit signing ===
echo ""
echo -e "${YELLOW}[5/14] GPG Commit Signing${NC}"
echo "--------------------------------------"

EXISTING_KEY=$(git config --global user.signingkey 2>/dev/null || true)
if [[ -n "$EXISTING_KEY" ]]; then
    success "GPG signing already configured (key: $EXISTING_KEY)"
else
    KEYS=$(gpg --list-secret-keys --keyid-format=long 2>/dev/null | grep "^sec" | awk '{print $2}' | cut -d/ -f2 | head -1)
    if [[ -n "$KEYS" ]]; then
        git config --global user.signingkey "$KEYS"
        git config --global commit.gpgsign true
        git config --global gpg.program gpg
        success "Configured git signing with existing key $KEYS"
    else
        info "Generating ed25519 GPG key..."
        gpg --full-generate-key --batch <<EOF
%no-protection
Key-Type: eddsa
Key-Curve: ed25519
Key-Usage: sign
Subkey-Type: eddsa
Subkey-Curve: ed25519
Subkey-Usage: sign
Name-Real: noc
Name-Email: adam@nocfa.net
Expire-Date: 1y
%commit
EOF
        NEW_KEY=$(gpg --list-secret-keys --keyid-format=long 2>/dev/null | grep "^sec" | awk '{print $2}' | cut -d/ -f2 | head -1)
        git config --global user.signingkey "$NEW_KEY"
        git config --global commit.gpgsign true
        git config --global gpg.program gpg
        success "GPG key generated: $NEW_KEY"
        warn "Add to Codeberg: Settings → SSH/GPG Keys → Manage GPG Keys"
        gpg --armor --export "$NEW_KEY"
    fi
fi

# === STEP 6: Git remotes ===
echo ""
echo -e "${YELLOW}[6/14] Git Remotes${NC}"
echo "--------------------------------------"

CURRENT_ORIGIN=$(git -C "$REPO_ROOT" remote get-url origin 2>/dev/null || true)
if echo "$CURRENT_ORIGIN" | grep -q "github.com"; then
    success "origin already set (GitHub)"
fi

if ! git -C "$REPO_ROOT" remote get-url codeberg &>/dev/null; then
    git -C "$REPO_ROOT" remote add codeberg ssh://git@codeberg.org/noc/noc-homelab.git
    success "codeberg remote added"
else
    success "codeberg remote exists"
fi

# Configure origin to push to both GitHub and Codeberg simultaneously
PUSH_URLS=$(git -C "$REPO_ROOT" remote get-url --push --all origin 2>/dev/null || true)
if ! echo "$PUSH_URLS" | grep -q "codeberg.org"; then
    GITHUB_URL=$(git -C "$REPO_ROOT" remote get-url origin 2>/dev/null)
    git -C "$REPO_ROOT" remote set-url --add --push origin "$GITHUB_URL"
    git -C "$REPO_ROOT" remote set-url --add --push origin "ssh://git@codeberg.org/noc/noc-homelab.git"
    success "origin configured to push to GitHub + Codeberg"
else
    success "origin already configured for dual push"
fi

# Ensure main branch tracks origin/main
git -C "$REPO_ROOT" branch --set-upstream-to=origin/main main 2>/dev/null && success "main branch tracking set to origin/main" || true

# Ensure Codeberg host key is in known_hosts
if ! grep -q "codeberg.org" "$HOME/.ssh/known_hosts" 2>/dev/null; then
    ssh-keyscan codeberg.org >> "$HOME/.ssh/known_hosts" 2>/dev/null
    success "Codeberg added to known_hosts"
fi

# === STEP 7: Codeberg auto-pull systemd timer ===
echo ""
echo -e "${YELLOW}[7/14] Codeberg Auto-pull Timer${NC}"
echo "--------------------------------------"

SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
mkdir -p "$SYSTEMD_USER_DIR"

for unit in git-autopull.service git-autopull.timer; do
    src="$REPO_ROOT/linux/systemd/$unit"
    dest="$SYSTEMD_USER_DIR/$unit"
    if [[ -f "$src" ]]; then
        ln -sf "$src" "$dest"
        info "  Linked: $unit"
    else
        warn "  Missing: $src"
    fi
done

systemctl --user daemon-reload
systemctl --user enable --now git-autopull.timer 2>/dev/null && success "git-autopull.timer enabled and running" || warn "Could not enable git-autopull.timer"

# === STEP 8: Verify SOPS Decryption ===
echo ""
echo -e "${YELLOW}[8/14] Verifying SOPS Decryption${NC}"
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
echo -e "${YELLOW}[9/14] Configuring FUSE${NC}"
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
echo -e "${YELLOW}[10/14] Creating Mount Point${NC}"
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
echo -e "${YELLOW}[11/14] Setting Up Rclone Config${NC}"
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
echo -e "${YELLOW}[12/14] Installing Media Pipeline Services${NC}"
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

# === STEP 13: Start Services ===
echo ""
echo -e "${YELLOW}[13/14] Starting Media Pipeline Services${NC}"
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

# === STEP 14: Claude Code memory symlink ===
echo ""
echo -e "${YELLOW}[14/14] Claude Code Shared Memory${NC}"
echo "--------------------------------------"

CLAUDE_MEM_DIR="$HOME/.claude/projects/-home-noc-noc-homelab/memory"
BEADS_MEM="$BEADS_ROOT/memory"

mkdir -p "$BEADS_MEM"

if [[ -L "$CLAUDE_MEM_DIR" ]] && [[ "$(readlink "$CLAUDE_MEM_DIR")" == "$BEADS_MEM" ]]; then
    success "  Claude memory already symlinked to beads"
elif [[ -d "$CLAUDE_MEM_DIR" ]]; then
    info "  Merging existing Claude memory into beads..."
    cp "$CLAUDE_MEM_DIR"/* "$BEADS_MEM/" 2>/dev/null || true
    rm -rf "$CLAUDE_MEM_DIR"
    ln -s "$BEADS_MEM" "$CLAUDE_MEM_DIR"
    success "  Claude memory merged and symlinked"
else
    mkdir -p "$(dirname "$CLAUDE_MEM_DIR")"
    ln -s "$BEADS_MEM" "$CLAUDE_MEM_DIR"
    success "  Claude memory symlinked to beads"
fi

# === SUMMARY ===
echo ""
echo -e "${MAGENTA}╔═══════════════════════════════════════════════╗${NC}"
echo -e "${MAGENTA}║   Setup Complete!                             ║${NC}"
echo -e "${MAGENTA}╚═══════════════════════════════════════════════╝${NC}"
echo ""

success "Framework:"
info "  Hooks:       SOPS encrypt-on-commit, decrypt-on-pull"
info "  Signing:     GPG commit signing"
info "  Remotes:     origin pushes to GitHub + Codeberg (dual push)"
info "  Auto-pull:   Codeberg every 5min (git-autopull.timer)"
info "  Memory:      Claude memory → noc-homelab-beads/memory/"
echo ""

success "Media pipeline next steps:"
info "  1. If Zurg config token is still a placeholder:"
info "     - Edit linux/services/zurg/config.yml with your Real-Debrid token"
info "     - Encrypt: sops -e -i linux/services/zurg/config.yml"
info "     - Restart: systemctl --user restart zurg"
echo ""
info "  2. Verify mount shows content (wait 10-60 seconds):"
info "     ls /mnt/zurg/movies"
info "     ls /mnt/zurg/shows"
echo ""
info "  3. Configure Emby/Jellyfin libraries:"
info "     Point libraries to: $REPO_ROOT/media/movies"
info "                         $REPO_ROOT/media/shows"
echo ""

success "Useful commands:"
info "  Media:    systemctl --user start/stop/restart zurg rclone-zurg"
info "  Autopull: systemctl --user status git-autopull.timer"
info "  Logs:     journalctl --user -u zurg -f"
info "  Beads:    bd ready | bd list | bd sync"
echo ""
