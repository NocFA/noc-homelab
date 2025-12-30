#!/bin/bash
# TeamSpeak 3 Server Auto-Update Script
# NOC Homelab - Automated version checking and updating

set -e

# Configuration
TS3_INSTALL_DIR="/Users/noc/teamspeak3-server_mac"
TS3_BACKUP_DIR="/Users/noc/noc-homelab/configs/teamspeak/backups"
LOG_FILE="/Users/noc/noc-homelab/logs/teamspeak-update.log"
DOWNLOAD_URL="https://files.teamspeak-services.com/releases/server"
PLATFORM="mac"

# Create log directory if it doesn't exist
mkdir -p "$(dirname "$LOG_FILE")"
mkdir -p "$TS3_BACKUP_DIR"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Get current installed version
get_current_version() {
    if [ -f "$TS3_INSTALL_DIR/.version" ]; then
        cat "$TS3_INSTALL_DIR/.version"
    else
        # Try to get from binary
        cd "$TS3_INSTALL_DIR" && ./ts3server version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || echo "unknown"
    fi
}

# Check for latest version from TeamSpeak downloads page
check_latest_version() {
    # Note: TeamSpeak doesn't provide a direct API for version checking
    # This is a placeholder - you may need to manually check or scrape their website
    # For now, we'll use a simple curl to check the download page

    log "Checking for latest TeamSpeak version..."

    # Try to get the latest version from the downloads page
    # This is a simplified approach - you may need to adjust based on TeamSpeak's actual website structure
    LATEST_VERSION=$(curl -s "https://teamspeak.com/en/downloads/" | grep -oE '3\.[0-9]+\.[0-9]+' | head -1 || echo "")

    if [ -z "$LATEST_VERSION" ]; then
        log "Could not determine latest version from website"
        return 1
    fi

    echo "$LATEST_VERSION"
}

# Backup current installation
backup_installation() {
    log "Creating backup of current installation..."

    BACKUP_NAME="teamspeak-backup-$(date '+%Y%m%d-%H%M%S').tar.gz"
    BACKUP_PATH="$TS3_BACKUP_DIR/$BACKUP_NAME"

    # Backup database, config, and logs
    cd "$TS3_INSTALL_DIR"
    tar -czf "$BACKUP_PATH" \
        ts3server.sqlitedb* \
        ts3server.ini \
        query_ip_allowlist.txt \
        query_ip_denylist.txt \
        ssh_host_rsa_key* \
        logs/ \
        2>/dev/null || true

    log "Backup created: $BACKUP_PATH"

    # Keep only last 5 backups
    cd "$TS3_BACKUP_DIR"
    ls -t teamspeak-backup-*.tar.gz | tail -n +6 | xargs rm -f 2>/dev/null || true
}

# Download and install update
install_update() {
    local VERSION=$1

    log "Downloading TeamSpeak Server version $VERSION..."

    # Create temp directory
    TEMP_DIR=$(mktemp -d)
    cd "$TEMP_DIR"

    # Download the latest version
    # Note: You'll need to update this URL based on actual TeamSpeak download links
    DOWNLOAD_FILE="teamspeak3-server_${PLATFORM}-${VERSION}.zip"

    log "Note: Automatic download not implemented - manual update required"
    log "Please download from: https://teamspeak.com/en/downloads/"

    # Clean up
    cd /
    rm -rf "$TEMP_DIR"

    return 1
}

# Stop TeamSpeak server
stop_server() {
    log "Stopping TeamSpeak server..."

    # Try launchctl first
    if launchctl list | grep -q "com.noc.teamspeak"; then
        launchctl stop com.noc.teamspeak 2>/dev/null || true
        sleep 2
    fi

    # Force kill if still running
    pkill -9 ts3server 2>/dev/null || true
    sleep 1

    log "TeamSpeak server stopped"
}

# Start TeamSpeak server
start_server() {
    log "Starting TeamSpeak server..."

    if launchctl list | grep -q "com.noc.teamspeak"; then
        launchctl start com.noc.teamspeak
    else
        cd "$TS3_INSTALL_DIR" && ./ts3server inifile=ts3server.ini &
    fi

    sleep 3
    log "TeamSpeak server started"
}

# Main update process
main() {
    log "=== TeamSpeak Update Check Started ==="

    CURRENT_VERSION=$(get_current_version)
    log "Current version: $CURRENT_VERSION"

    # Save current version to file for future reference
    echo "$CURRENT_VERSION" > "$TS3_INSTALL_DIR/.version"

    # For manual updates, we'll just log the current state
    log "Update check completed. Manual update required if new version available."
    log "Check: https://teamspeak.com/en/downloads/"
    log "Current installation: $TS3_INSTALL_DIR"

    # Perform backup anyway
    backup_installation

    log "=== Update Check Completed ==="
}

# Run main function
main "$@"
