#!/usr/bin/env bash
# macOS Homelab Setup Script (noc-local)
# Sets up the full homelab framework: SOPS encryption, beads, GPG signing,
# git remotes, auto-pull, LaunchAgents, and Claude Code memory.
#
# Usage: ./setup/setup-macos.sh
#
# Prerequisites (install manually first):
#   - Homebrew: https://brew.sh
#   - Claude Code: https://claude.ai/code
#   - noc-homelab-beads age key placed at noc-homelab-beads/homelab.agekey

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'

success() { echo -e "${GREEN}  ✓ $1${NC}"; }
error()   { echo -e "${RED}  ✗ $1${NC}"; }
info()    { echo -e "${CYAN}  → $1${NC}"; }
warn()    { echo -e "${YELLOW}  ! $1${NC}"; }
section() { echo -e "\n${YELLOW}[$1] $2${NC}\n$(printf '%.0s─' {1..50})"; }

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BEADS_ROOT="$REPO_ROOT/noc-homelab-beads"
AGE_KEY="$BEADS_ROOT/homelab.agekey"
BREW="$(command -v brew 2>/dev/null || echo /opt/homebrew/bin/brew)"

export SOPS_AGE_KEY_FILE="$AGE_KEY"

echo ""
echo -e "${MAGENTA}╔══════════════════════════════════════════╗${NC}"
echo -e "${MAGENTA}║   macOS Homelab Setup — noc-local        ║${NC}"
echo -e "${MAGENTA}╚══════════════════════════════════════════╝${NC}"
echo ""
info "Repo root: $REPO_ROOT"

# ── 1: Prerequisites ─────────────────────────────────────────────────────────
section "1/9" "Prerequisites"

missing=0

if "$BREW" --version &>/dev/null; then
    success "Homebrew found"
else
    error "Homebrew not found — install from https://brew.sh first"
    exit 1
fi

for pkg in sops age gpg; do
    if "$BREW" list "$pkg" &>/dev/null 2>&1 || command -v "$pkg" &>/dev/null; then
        success "$pkg installed"
    else
        info "Installing $pkg via Homebrew..."
        "$BREW" install "$pkg"
        success "$pkg installed"
    fi
done

if command -v bd &>/dev/null; then
    success "beads (bd) found: $(bd --version 2>/dev/null | head -1)"
else
    warn "beads (bd) not found — install from https://github.com/NocFA/beads"
    warn "  Or: curl -fsSL https://beads.sh/install | bash"
    ((missing++)) || true
fi

if [[ -f "$AGE_KEY" ]]; then
    success "Age key found: $AGE_KEY"
else
    error "Age key NOT found at $AGE_KEY"
    info "  Copy homelab.agekey to $AGE_KEY before continuing"
    exit 1
fi

if [[ $missing -gt 0 ]]; then
    warn "$missing prerequisite(s) missing — install them and re-run"
    read -rp "Continue anyway? (y/n) " reply
    [[ "$reply" == "y" ]] || exit 1
fi

# ── 2: noc-homelab-beads git repo ────────────────────────────────────────────
section "2/9" "Beads Sync Repo"

if [[ -d "$BEADS_ROOT/.git" ]]; then
    success "noc-homelab-beads already a git repo"
    git -C "$BEADS_ROOT" pull origin main -q 2>/dev/null && info "Pulled latest" || true
else
    info "Initializing noc-homelab-beads as git repo..."
    AGE_KEY_BACKUP=$(cat "$AGE_KEY")
    git -C "$BEADS_ROOT" init -b main -q
    git -C "$BEADS_ROOT" remote add origin https://github.com/NocFA/noc-homelab-beads.git
    git -C "$BEADS_ROOT" fetch origin main -q
    git -C "$BEADS_ROOT" reset --hard origin/main -q
    # Restore age key if git reset removed it
    if [[ ! -f "$AGE_KEY" ]]; then
        echo "$AGE_KEY_BACKUP" > "$AGE_KEY"
        chmod 600 "$AGE_KEY"
    fi
    success "noc-homelab-beads initialized and pulled"
fi

# ── 3: Git hooks ─────────────────────────────────────────────────────────────
section "3/9" "Git Hooks (SOPS + Beads)"

HOOKS_DIR="$REPO_ROOT/.git/hooks"
SOPS_BIN="$(command -v sops 2>/dev/null || echo /opt/homebrew/bin/sops)"

install_hook() {
    local name="$1"
    local src="$REPO_ROOT/.git/hooks/$name"
    # Backup existing if it's not ours
    if [[ -f "$src" ]] && ! grep -q "SOPS auto-encrypt\|SOPS auto-decrypt" "$src" 2>/dev/null; then
        cp "$src" "$src.backup"
        info "Backed up existing $name to $name.backup"
    fi
}

# pre-commit: SOPS encrypt + beads
install_hook "pre-commit"
cat > "$HOOKS_DIR/pre-commit" << 'HOOK'
#!/usr/bin/env sh
# Pre-commit hook: SOPS auto-encrypt + beads sync

REPO_ROOT="$(git rev-parse --show-toplevel)"
SOPS_AGE_KEY_FILE="$REPO_ROOT/noc-homelab-beads/homelab.agekey"
SOPS="$(command -v sops 2>/dev/null || echo /opt/homebrew/bin/sops)"

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

if command -v bd >/dev/null 2>&1; then
    exec bd hook pre-commit "$@"
fi
HOOK
chmod +x "$HOOKS_DIR/pre-commit"
success "pre-commit hook installed"

# post-merge: SOPS decrypt
install_hook "post-merge"
cat > "$HOOKS_DIR/post-merge" << 'HOOK'
#!/usr/bin/env sh
# Post-merge hook: SOPS auto-decrypt + beads sync

REPO_ROOT="$(git rev-parse --show-toplevel)"
SOPS_AGE_KEY_FILE="$REPO_ROOT/noc-homelab-beads/homelab.agekey"
SOPS="$(command -v sops 2>/dev/null || echo /opt/homebrew/bin/sops)"

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
                if SOPS_AGE_KEY_FILE="$SOPS_AGE_KEY_FILE" "$SOPS" -d -i "$full_path" 2>/dev/null; then
                    decrypted=$((decrypted + 1))
                fi
            fi
        fi
    done
    [ $decrypted -gt 0 ] && echo "SOPS: auto-decrypted $decrypted file(s) to plaintext"
fi

if command -v bd >/dev/null 2>&1; then
    exec bd hook post-merge "$@"
fi
HOOK
chmod +x "$HOOKS_DIR/post-merge"
success "post-merge hook installed"

# post-checkout: SOPS decrypt on branch switch
install_hook "post-checkout"
cat > "$HOOKS_DIR/post-checkout" << 'HOOK'
#!/usr/bin/env sh
# Post-checkout hook: bd sync + SOPS auto-decrypt

if command -v bd >/dev/null 2>&1; then
    bd hook post-checkout "$@"
fi

FLAG="${3:-0}"
[ "$FLAG" != "1" ] && exit 0

SOPS_BIN="$(command -v sops 2>/dev/null || echo /opt/homebrew/bin/sops)"
REPO_ROOT="$(git rev-parse --show-toplevel)"
SOPS_AGE_KEY_FILE="$REPO_ROOT/noc-homelab-beads/homelab.agekey"

if [ -x "$SOPS_BIN" ] && [ -f "$SOPS_AGE_KEY_FILE" ]; then
    changed=$(git diff-tree -r --name-only --no-commit-id ORIG_HEAD HEAD 2>/dev/null)
    for f in $changed; do
        full_path="$REPO_ROOT/$f"
        [ -f "$full_path" ] || continue
        if grep -q 'ENC\[AES256_GCM,' "$full_path" 2>/dev/null; then
            SOPS_AGE_KEY_FILE="$SOPS_AGE_KEY_FILE" "$SOPS_BIN" -d -i "$full_path" 2>/dev/null && echo "SOPS: decrypted $f"
        fi
    done
fi
HOOK
chmod +x "$HOOKS_DIR/post-checkout"
success "post-checkout hook installed"

# Verify pre-push hook exists (bd shim)
if [[ ! -f "$HOOKS_DIR/pre-push" ]]; then
    cat > "$HOOKS_DIR/pre-push" << 'HOOK'
#!/usr/bin/env sh
if command -v bd >/dev/null 2>&1; then
    exec bd hook pre-push "$@"
fi
HOOK
    chmod +x "$HOOKS_DIR/pre-push"
    success "pre-push hook installed"
else
    success "pre-push hook exists"
fi

# ── 4: GPG commit signing ─────────────────────────────────────────────────────
section "4/9" "GPG Commit Signing"

GPG="$("$BREW" --prefix)/bin/gpg"
EXISTING_KEY=$(git config --global user.signingkey 2>/dev/null || true)

if [[ -n "$EXISTING_KEY" ]]; then
    success "GPG signing already configured (key: $EXISTING_KEY)"
else
    # Check for existing keys
    KEYS=$("$GPG" --list-secret-keys --keyid-format=long 2>/dev/null | grep "^sec" | awk '{print $2}' | cut -d/ -f2 | head -1)
    if [[ -n "$KEYS" ]]; then
        info "Found existing GPG key: $KEYS"
        git config --global user.signingkey "$KEYS"
        git config --global commit.gpgsign true
        git config --global gpg.program "$GPG"
        success "Configured git to use existing key $KEYS"
        info "Export public key to add to Codeberg: $GPG --armor --export $KEYS"
    else
        info "Generating new ed25519 GPG key for noc@noc-local..."
        "$GPG" --full-generate-key --batch <<EOF
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
        NEW_KEY=$("$GPG" --list-secret-keys --keyid-format=long 2>/dev/null | grep "^sec" | awk '{print $2}' | cut -d/ -f2 | head -1)
        git config --global user.signingkey "$NEW_KEY"
        git config --global commit.gpgsign true
        git config --global gpg.program "$GPG"
        success "GPG key generated: $NEW_KEY"
        warn "Add public key to Codeberg: Settings → SSH/GPG Keys → Manage GPG Keys"
        "$GPG" --armor --export "$NEW_KEY"
    fi
fi

# ── 5: Git remotes ────────────────────────────────────────────────────────────
section "5/9" "Git Remotes"

CURRENT_ORIGIN=$(git -C "$REPO_ROOT" remote get-url origin 2>/dev/null || true)
if echo "$CURRENT_ORIGIN" | grep -q "codeberg"; then
    success "origin already points to Codeberg"
else
    git -C "$REPO_ROOT" remote add origin ssh://git@codeberg.org/noc/noc-homelab.git 2>/dev/null || \
        git -C "$REPO_ROOT" remote set-url origin ssh://git@codeberg.org/noc/noc-homelab.git
    success "origin set to Codeberg"
fi

if git -C "$REPO_ROOT" remote get-url github &>/dev/null; then
    success "github remote already configured"
else
    git -C "$REPO_ROOT" remote add github https://github.com/NocFA/noc-homelab.git
    success "github remote added (GitHub)"
fi

# ── 6: LaunchAgents ───────────────────────────────────────────────────────────
section "6/9" "LaunchAgents"

LAUNCH_AGENTS_SRC="$REPO_ROOT/launchagents"
LAUNCH_AGENTS_DEST="$HOME/Library/LaunchAgents"
mkdir -p "$LAUNCH_AGENTS_DEST"

for plist in "$LAUNCH_AGENTS_SRC"/*.plist; do
    name=$(basename "$plist")
    dest="$LAUNCH_AGENTS_DEST/$name"
    if [[ -L "$dest" ]] && [[ "$(readlink "$dest")" == "$plist" ]]; then
        success "$name already linked"
    else
        ln -sf "$plist" "$dest"
        info "Linked $name"
        launchctl unload "$dest" 2>/dev/null || true
        launchctl load "$dest" 2>/dev/null && success "Loaded $name" || warn "Could not load $name (may need manual load)"
    fi
done

# ── 7: Auto-pull from Codeberg ────────────────────────────────────────────────
section "7/9" "Codeberg Auto-pull"

AUTOPULL_PLIST="$LAUNCH_AGENTS_DEST/com.noc.git-autopull.plist"
if launchctl list com.noc.git-autopull &>/dev/null 2>&1; then
    success "git-autopull already running"
else
    if [[ -f "$AUTOPULL_PLIST" ]]; then
        launchctl load "$AUTOPULL_PLIST" && success "git-autopull loaded" || warn "Could not load git-autopull"
    else
        warn "git-autopull plist not found — ensure launchagents/com.noc.git-autopull.plist is in repo"
    fi
fi

mkdir -p "$REPO_ROOT/logs"

# ── 8: SOPS decrypt existing files ────────────────────────────────────────────
section "8/9" "SOPS Decrypt Existing Configs"

SOPS_CMD="$(command -v sops 2>/dev/null || echo /opt/homebrew/bin/sops)"

if [[ -x "$SOPS_CMD" ]] && [[ -f "$AGE_KEY" ]]; then
    decrypted=0
    while IFS= read -r -d '' f; do
        if grep -q 'ENC\[AES256_GCM,' "$f" 2>/dev/null; then
            if SOPS_AGE_KEY_FILE="$AGE_KEY" "$SOPS_CMD" -d -i "$f" 2>/dev/null; then
                info "Decrypted: ${f#$REPO_ROOT/}"
                git -C "$REPO_ROOT" update-index --skip-worktree "$f" 2>/dev/null || true
                ((decrypted++)) || true
            fi
        fi
    done < <(git -C "$REPO_ROOT" ls-files -z)
    success "Decrypted $decrypted SOPS-encrypted file(s)"
else
    warn "Skipping SOPS decrypt (sops or age key missing)"
fi

# ── 9: Claude Code memory symlink ─────────────────────────────────────────────
section "9/9" "Claude Code Shared Memory"

CLAUDE_MEM_DIR="$HOME/.claude/projects/-Users-noc-noc-homelab/memory"
BEADS_MEM="$BEADS_ROOT/memory"

mkdir -p "$BEADS_MEM"

if [[ -L "$CLAUDE_MEM_DIR" ]] && [[ "$(readlink "$CLAUDE_MEM_DIR")" == "$BEADS_MEM" ]]; then
    success "Claude memory already symlinked to beads"
elif [[ -d "$CLAUDE_MEM_DIR" ]]; then
    info "Merging existing Claude memory into beads..."
    cp "$CLAUDE_MEM_DIR"/* "$BEADS_MEM/" 2>/dev/null || true
    rm -rf "$CLAUDE_MEM_DIR"
    ln -s "$BEADS_MEM" "$CLAUDE_MEM_DIR"
    success "Claude memory merged and symlinked"
else
    mkdir -p "$(dirname "$CLAUDE_MEM_DIR")"
    ln -s "$BEADS_MEM" "$CLAUDE_MEM_DIR"
    success "Claude memory symlinked to beads"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${MAGENTA}╔══════════════════════════════════════════╗${NC}"
echo -e "${MAGENTA}║   Setup Complete                         ║${NC}"
echo -e "${MAGENTA}╚══════════════════════════════════════════╝${NC}"
echo ""
success "Hooks:       SOPS encrypt-on-commit, decrypt-on-pull"
success "Signing:     GPG commit signing configured"
success "Remotes:     origin=Codeberg, github=GitHub"
success "Auto-pull:   Codeberg every 5min via launchd"
success "Memory:      Claude memory synced via beads repo"
echo ""
info "Next steps:"
info "  - Push your SSH key to Codeberg if not done"
info "  - Add GPG public key to Codeberg if new key was generated"
info "  - Start the dashboard: launchctl load ~/Library/LaunchAgents/com.noc.dashboard.plist"
info "  - Check logs: tail -f $REPO_ROOT/logs/git-autopull.log"
echo ""
