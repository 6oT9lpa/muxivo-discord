#!/usr/bin/env bash
set -euo pipefail

ARCHIVE="${ARCHIVE:-/tmp/muxivo-discord-release.tar.gz}"
ROOT_TMP="${ROOT_TMP:-/root/tmp}"
APP_DIR="${APP_DIR:-/opt/muxivo-discord}"
BACKUP_DIR="${BACKUP_DIR:-/opt}"
BACKUP="$BACKUP_DIR/muxivo-discord.backup-$(date +%Y%m%d%H%M%S).tgz"
ROOT_ARCHIVE="$ROOT_TMP/muxivo-discord-release.tar.gz"
SERVICES=(${SERVICES:-muxivo-discord-bot.service muxivo-discord-activity.service})

log() {
    printf '[muxivo-discord-deploy] %s\n' "$*"
}

mkdir -p "$ROOT_TMP"

log "Copy archive to root tmp..."
cp "$ARCHIVE" "$ROOT_ARCHIVE"

if [ -d "$APP_DIR" ]; then
    log "Create backup..."
    tar -C "$(dirname "$APP_DIR")" -czf "$BACKUP" "$(basename "$APP_DIR")"
else
    log "App directory does not exist yet, backup skipped."
fi

log "Stop services..."
for service in "${SERVICES[@]}"; do
    systemctl stop "$service" || true
done

log "Extract new files over existing project..."
mkdir -p "$APP_DIR"
tar -xzf "$ROOT_ARCHIVE" -C "$APP_DIR"

log "Start services..."
for service in "${SERVICES[@]}"; do
    systemctl start "$service"
done

log "Status:"
for service in "${SERVICES[@]}"; do
    systemctl is-active "$service"
done

log "Backup created: ${BACKUP:-none}"
log "Done"
