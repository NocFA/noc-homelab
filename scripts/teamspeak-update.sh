#!/bin/bash
# TeamSpeak Server Update Script (Docker)
# NOC Homelab - Pulls latest image, backs up data, recreates container

set -e

CONTAINER_NAME="teamspeak6-server"
IMAGE="teamspeaksystems/teamspeak6-server:latest"
DATA_DIR="/Users/noc/noc-homelab/services/teamspeak6/data"
BACKUP_DIR="/Users/noc/noc-homelab/configs/teamspeak/backups"
LOG_FILE="/Users/noc/noc-homelab/logs/teamspeak-update.log"
KEEP_BACKUPS=5

mkdir -p "$(dirname "$LOG_FILE")" "$BACKUP_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

backup_data() {
    local name="teamspeak-backup-$(date '+%Y%m%d-%H%M%S').tar.gz"
    local path="$BACKUP_DIR/$name"
    log "Backing up data directory to $path"
    tar -czf "$path" -C "$(dirname "$DATA_DIR")" "$(basename "$DATA_DIR")"
    # Rotate
    ls -t "$BACKUP_DIR"/teamspeak-backup-*.tar.gz 2>/dev/null | tail -n +$((KEEP_BACKUPS + 1)) | xargs rm -f 2>/dev/null || true
}

current_image_id() {
    docker inspect "$CONTAINER_NAME" --format '{{.Image}}' 2>/dev/null || echo ""
}

main() {
    log "=== TeamSpeak Update Check Started ==="

    if ! docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        log "ERROR: container '$CONTAINER_NAME' not found — manual deployment required"
        exit 1
    fi

    local before_id
    before_id=$(current_image_id)
    log "Current container image id: $before_id"

    log "Pulling latest image: $IMAGE"
    docker pull "$IMAGE"

    local latest_id
    latest_id=$(docker image inspect "$IMAGE" --format '{{.Id}}' 2>/dev/null || echo "")

    if [ -n "$before_id" ] && [ "$before_id" = "$latest_id" ]; then
        log "Already up to date — no container recreation needed"
        log "=== Update Check Completed (no-op) ==="
        return 0
    fi

    backup_data

    log "Recreating container to pick up new image"
    # Capture the run command from the live container, swap image, then recreate.
    # Uses `docker container update`-incompatible fields, so we stop + rm + run.
    local run_args
    run_args=$(docker inspect "$CONTAINER_NAME" --format '
--name={{.Name}}
{{- range $p, $conf := .HostConfig.PortBindings }}{{ range $conf }} -p {{ .HostPort }}:{{ $p }}{{ end }}{{ end }}
{{- range .Mounts }} -v {{ .Source }}:{{ .Destination }}{{ end }}
{{- range .Config.Env }} -e {{ . }}{{ end }}
{{- if .HostConfig.RestartPolicy.Name }} --restart={{ .HostConfig.RestartPolicy.Name }}{{ end }}
' | tr -s '[:space:]' ' ' | sed 's|--name=/|--name=|')

    docker stop "$CONTAINER_NAME" >/dev/null
    docker rm "$CONTAINER_NAME" >/dev/null

    # shellcheck disable=SC2086
    docker run -d $run_args "$IMAGE" >/dev/null

    log "Container recreated on new image"
    log "=== Update Completed ==="
}

main "$@"
