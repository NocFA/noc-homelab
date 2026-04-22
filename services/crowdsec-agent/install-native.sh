#!/usr/bin/env bash
# Builds and installs the CrowdSec agent natively under /opt/homebrew on
# Apple Silicon macOS, then registers it as a LaunchAgent. Agent-only
# mode — forwards alerts to the central LAPI defined in .env.
#
# Idempotent. Re-running upgrades binaries and refreshes config, but
# will not overwrite an existing local_api_credentials.yaml (so you
# keep the password already issued by the LAPI).
#
# Prereqs: Apple Silicon mac, Homebrew, repo checked out at ~/noc-homelab
# or adjust REPO below. Machine credentials already issued on the LAPI
# host and filled into .env.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/../.." && pwd)"
AGENT_DIR="$SCRIPT_DIR"
ENV_FILE="$AGENT_DIR/.env"
PREFIX="/opt/homebrew"
BUILD_DIR="${HOME}/dev/crowdsec"
BUILD_TAG="v1.7.7"
LAUNCH_AGENT="$REPO/launchagents/com.noc.crowdsec-agent.plist"
LOG_DIR="$HOME/Library/Logs/noc-homelab"

echo "==> CrowdSec agent native install (repo=$REPO)"

# 1. Preflight
command -v brew >/dev/null || { echo "ERROR: brew not found in PATH"; exit 1; }
[ "$(uname -m)" = "arm64" ] || { echo "ERROR: this script assumes Apple Silicon (/opt/homebrew)"; exit 1; }
[ -f "$ENV_FILE" ] || { echo "ERROR: missing $ENV_FILE — copy .env.example and fill it"; exit 1; }
[ -f "$LAUNCH_AGENT" ] || { echo "ERROR: missing $LAUNCH_AGENT"; exit 1; }

# 2. Build dependencies — install only if absent
for pkg in go make re2 pkg-config; do
  if ! brew list --formula "$pkg" >/dev/null 2>&1; then
    echo "==> brew install $pkg"
    brew install "$pkg"
  fi
done

# 3. Build binaries if they're missing or older than the tracked tag
NEEDS_BUILD=0
if [ ! -x "$PREFIX/bin/crowdsec" ] || [ ! -x "$PREFIX/bin/cscli" ]; then
  NEEDS_BUILD=1
else
  INSTALLED_VERSION="$("$PREFIX/bin/crowdsec" -version 2>&1 | awk '/^version:/{print $2}')"
  case "$INSTALLED_VERSION" in
    "$BUILD_TAG"*) echo "==> crowdsec $INSTALLED_VERSION already installed";;
    *) echo "==> installed crowdsec=$INSTALLED_VERSION, target=$BUILD_TAG — rebuilding"; NEEDS_BUILD=1;;
  esac
fi

if [ "$NEEDS_BUILD" -eq 1 ]; then
  if [ ! -d "$BUILD_DIR/.git" ]; then
    echo "==> cloning crowdsec $BUILD_TAG into $BUILD_DIR"
    git clone --depth 1 --branch "$BUILD_TAG" https://github.com/crowdsecurity/crowdsec.git "$BUILD_DIR"
  else
    echo "==> updating $BUILD_DIR to $BUILD_TAG"
    git -C "$BUILD_DIR" fetch --depth 1 origin "refs/tags/$BUILD_TAG:refs/tags/$BUILD_TAG"
    git -C "$BUILD_DIR" checkout "$BUILD_TAG"
  fi
  echo "==> building crowdsec + cscli (baking default config+data dirs into the binaries)"
  ( cd "$BUILD_DIR" && gmake build \
      DEFAULT_CONFIGDIR="$PREFIX/etc/crowdsec" \
      DEFAULT_DATADIR="$PREFIX/var/lib/crowdsec/data" )
  cp "$BUILD_DIR/cmd/crowdsec/crowdsec" "$PREFIX/bin/crowdsec"
  cp "$BUILD_DIR/cmd/crowdsec-cli/cscli" "$PREFIX/bin/cscli"
  "$PREFIX/bin/crowdsec" -version | head -3
fi

# 4. Config scaffolding
mkdir -p \
  "$PREFIX/etc/crowdsec/acquis.d" \
  "$PREFIX/etc/crowdsec/hub" \
  "$PREFIX/etc/crowdsec/notifications" \
  "$PREFIX/var/lib/crowdsec/data"

# Copy the grok patterns library from the upstream source tree.
if [ -d "$BUILD_DIR/config/patterns" ]; then
  mkdir -p "$PREFIX/etc/crowdsec/patterns"
  cp -r "$BUILD_DIR/config/patterns/." "$PREFIX/etc/crowdsec/patterns/"
fi

# Copy default simulation.yaml (empty allowlist); agent needs it present.
if [ ! -f "$PREFIX/etc/crowdsec/simulation.yaml" ] && [ -f "$BUILD_DIR/config/simulation.yaml" ]; then
  cp "$BUILD_DIR/config/simulation.yaml" "$PREFIX/etc/crowdsec/simulation.yaml"
fi

# config.yaml — generated inline so a fresh clone doesn't need any
# extra tracked template. Agent-only mode (api.server.enable=false) and
# absolute paths under /opt/homebrew so cscli / crowdsec work without -c.
cat > "$PREFIX/etc/crowdsec/config.yaml" <<'EOF'
common:
  daemonize: false
  log_media: stdout
  log_level: info
config_paths:
  config_dir: /opt/homebrew/etc/crowdsec/
  data_dir: /opt/homebrew/var/lib/crowdsec/data/
  simulation_path: /opt/homebrew/etc/crowdsec/simulation.yaml
  hub_dir: /opt/homebrew/etc/crowdsec/hub/
  index_path: /opt/homebrew/etc/crowdsec/hub/.index.json
  notification_dir: /opt/homebrew/etc/crowdsec/notifications/
  plugin_dir: /opt/homebrew/lib/crowdsec/plugins/
  pattern_dir: /opt/homebrew/etc/crowdsec/patterns/
crowdsec_service:
  acquisition_dir: /opt/homebrew/etc/crowdsec/acquis.d
  parser_routines: 1
cscli:
  output: human
  color: auto
db_config:
  log_level: info
  type: sqlite
  db_path: /opt/homebrew/var/lib/crowdsec/data/crowdsec.db
  flush:
    max_items: 5000
    max_age: 7d
api:
  client:
    insecure_skip_verify: false
    credentials_path: /opt/homebrew/etc/crowdsec/local_api_credentials.yaml
  server:
    enable: false
prometheus:
  enabled: false
EOF

# Acquisition — tail the legacy syslog file for sshd auth activity.
install -m 0644 "$AGENT_DIR/acquis.d/system-log.yaml" "$PREFIX/etc/crowdsec/acquis.d/system-log.yaml"

# 5. LAPI credentials — render from .env only if the target is absent.
# We never overwrite an existing creds file: the password was issued once
# by the LAPI and re-rendering can silently clobber a rotated secret.
CREDS_FILE="$PREFIX/etc/crowdsec/local_api_credentials.yaml"
if [ ! -f "$CREDS_FILE" ]; then
  echo "==> rendering $CREDS_FILE from .env"
  # shellcheck disable=SC1090
  ( set -a; . "$ENV_FILE"; set +a
    umask 077
    cat > "$CREDS_FILE" <<EOF
url: ${LOCAL_API_URL}
login: ${AGENT_USERNAME}
password: ${AGENT_PASSWORD}
EOF
  )
  chmod 600 "$CREDS_FILE"
else
  echo "==> $CREDS_FILE already exists, leaving as-is"
fi

# 6. Hub index + collections
"$PREFIX/bin/cscli" hub update
"$PREFIX/bin/cscli" collections install \
  crowdsecurity/sshd \
  crowdsecurity/base-http-scenarios || true

# 7. LaunchAgent
mkdir -p "$LOG_DIR" "$HOME/Library/LaunchAgents"
ln -sf "$LAUNCH_AGENT" "$HOME/Library/LaunchAgents/com.noc.crowdsec-agent.plist"
launchctl unload "$HOME/Library/LaunchAgents/com.noc.crowdsec-agent.plist" 2>/dev/null || true
launchctl load    "$HOME/Library/LaunchAgents/com.noc.crowdsec-agent.plist"

# 8. Verify
sleep 3
"$PREFIX/bin/cscli" lapi status
launchctl list | grep com.noc.crowdsec-agent || { echo "ERROR: LaunchAgent not loaded"; exit 1; }

echo
echo "==> Done. On noc-tux run 'sudo cscli machines list' to confirm fresh heartbeat."
echo "    Tail logs with: tail -f $LOG_DIR/crowdsec-agent.error.log"
