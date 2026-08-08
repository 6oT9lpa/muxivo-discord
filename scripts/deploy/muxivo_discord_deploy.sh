#!/usr/bin/env bash
# Deploy an Muxivo Discord release without replacing secrets or runtime data.
set -euo pipefail

ARCHIVE="${ARCHIVE:-/tmp/muxivo-discord-release.tar.gz}"
APP_DIR="${APP_DIR:-/opt/muxivo-discord}"
BACKUP="/opt/muxivo-discord.backup-$(date +%Y%m%d%H%M%S).tgz"
SERVICES=(muxivo-discord-bot muxivo-discord-activity)

log() { printf '[muxivo-discord-deploy] %s\n' "$*"; }

if [ -d "$APP_DIR" ]; then
  log "Creating backup: $BACKUP"
  tar --exclude='muxivo-discord/.venv' --exclude='muxivo-discord/.env' --exclude='muxivo-discord/data' --exclude='muxivo-discord/logs' \
    -C "$(dirname "$APP_DIR")" -czf "$BACKUP" "$(basename "$APP_DIR")"
fi

log "Stopping services"
systemctl stop "${SERVICES[@]}"
trap 'systemctl start "${SERVICES[@]}" || true' EXIT

log "Extracting release"
tar -xzf "$ARCHIVE" -C "$APP_DIR"
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"

# Migrations run as the service account so database-created files retain the
# same ownership and the production .env remains the sole source of secrets.
su -s /bin/bash muxivo-discord -c "cd '$APP_DIR' && set -a && . ./.env && set +a && ./.venv/bin/alembic upgrade head"

chown -R muxivo-discord:muxivo-discord "$APP_DIR"
systemctl start "${SERVICES[@]}"
trap - EXIT
systemctl is-active "${SERVICES[@]}"
log "Deployment complete; backup: $BACKUP"
