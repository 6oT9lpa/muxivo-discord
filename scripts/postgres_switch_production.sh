#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/muxivo-discord}"
ENV_FILE="${ENV_FILE:-$APP_DIR/.env}"
POSTGRES_URL="${POSTGRES_URL:?POSTGRES_URL is required}"
BACKUP="$ENV_FILE.backup-$(date +%Y%m%d%H%M%S)"
SERVICES=(${SERVICES:-muxivo-discord-bot.service muxivo-discord-activity.service})

cp "$ENV_FILE" "$BACKUP"

if grep -q '^DATABASE_URL=' "$ENV_FILE"; then
    sed -i "s|^DATABASE_URL=.*|DATABASE_URL=$POSTGRES_URL|" "$ENV_FILE"
else
    printf '\nDATABASE_URL=%s\n' "$POSTGRES_URL" >> "$ENV_FILE"
fi

for service in "${SERVICES[@]}"; do
    systemctl restart "$service"
done

for service in "${SERVICES[@]}"; do
    systemctl is-active "$service"
done

echo "Production switched to PostgreSQL. Env backup: $BACKUP"
