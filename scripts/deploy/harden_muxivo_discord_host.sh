#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/muxivo-discord}"
SERVICE_DIR="${SERVICE_DIR:-/etc/systemd/system}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_USER="${RUNTIME_USER:-muxivo-discord}"

if [[ "${EUID}" -ne 0 ]]; then
    echo "This script must run as root." >&2
    exit 1
fi

getent group "${RUNTIME_USER}" >/dev/null || groupadd --system "${RUNTIME_USER}"
id -u "${RUNTIME_USER}" >/dev/null 2>&1 || useradd --system --gid "${RUNTIME_USER}" --home-dir "${APP_DIR}" --shell /usr/sbin/nologin "${RUNTIME_USER}"

install -m 0644 "${SCRIPT_DIR}/muxivo-discord-bot.service" "${SERVICE_DIR}/muxivo-discord-bot.service"
install -m 0644 "${SCRIPT_DIR}/muxivo-discord-activity.service" "${SERVICE_DIR}/muxivo-discord-activity.service"

mkdir -p "${APP_DIR}/data" "${APP_DIR}/logs"
find "${APP_DIR}" -path "${APP_DIR}/data" -prune -o -path "${APP_DIR}/logs" -prune -o -exec chmod go-w {} +
chown -R "${RUNTIME_USER}:${RUNTIME_USER}" "${APP_DIR}/data" "${APP_DIR}/logs"
chmod 0750 "${APP_DIR}/data" "${APP_DIR}/logs"
sed -i 's/\r$//' "${APP_DIR}/.env"
chown root:"${RUNTIME_USER}" "${APP_DIR}/.env"
chmod 0640 "${APP_DIR}/.env"

systemctl daemon-reload
systemctl restart muxivo-discord-bot.service muxivo-discord-activity.service
systemctl is-active --quiet muxivo-discord-bot.service
systemctl is-active --quiet muxivo-discord-activity.service
