#!/usr/bin/env bash
# Deploy an OmniBot release without replacing secrets or runtime data.
set -euo pipefail

ARCHIVE="${ARCHIVE:-/tmp/omnibot-release.tar.gz}"
APP_DIR="${APP_DIR:-/opt/omnibot}"
BACKUP="/opt/omnibot.backup-$(date +%Y%m%d%H%M%S).tgz"
SERVICES=(omnibot-bot omnibot-activity)

log() { printf '[omnibot-deploy] %s\n' "$*"; }

if [ -d "$APP_DIR" ]; then
  log "Creating backup: $BACKUP"
  tar --exclude='omnibot/.venv' --exclude='omnibot/.env' --exclude='omnibot/data' --exclude='omnibot/logs' \
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
su -s /bin/bash omnibot -c "cd '$APP_DIR' && set -a && . ./.env && set +a && ./.venv/bin/alembic upgrade head"

chown -R omnibot:omnibot "$APP_DIR"
systemctl start "${SERVICES[@]}"
trap - EXIT
systemctl is-active "${SERVICES[@]}"
log "Deployment complete; backup: $BACKUP"
