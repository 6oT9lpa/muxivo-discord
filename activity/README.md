# Muxivo DS Activity

This folder contains the Muxivo DS Activity control panel for Muxivo Discord.

The client supports English and Russian locales. Users can switch language next
to the theme control in both public and panel headers. The preference is stored
locally in the browser. Translation dictionaries live in
`client/src/i18n/locales`, while `client/src/i18n/index.ts` owns locale selection,
fallbacks, interpolation, and document language updates.

The Activity is a Vue 3 frontend loaded inside Discord and a FastAPI backend that handles OAuth code exchange, RBAC checks, Discord API access, settings persistence, and Activity audit logging. Protected workspace routes are intended to work inside Discord only.

## Structure

- `client/` - Vue 3 + Vite + TypeScript frontend.
- `server/` - FastAPI backend for OAuth, session building, RBAC, bot settings, logs, Creator Alerts, Dev Blog, welcome, stats, voice rooms, and Discord reference data.

## Current Panels

- Dashboard - module overview and recent Activity audit events.
- Access Control - Activity roles and module permissions.
- Activity Role Mapping (legacy route key: `role-panels`) - synchronized Discord roles mapped to Activity access roles; this is distinct from public Discord role-panel messages.
- Welcome Alerts - welcome embed settings, reset, and test send.
- Creator Alerts - Twitch/YouTube/Kick sources, templates, preview, button labels, saved source cards.
- Dev Blog - drafts, Components V2 publishing, image galleries, Dev Blog ping.
- Logs - server logs and Activity audit changes.
- Server Stats - statistics available from the bot API.
- Voice Rooms - administrator/moderator room management and user-owned room controls.
- Bot Settings - channel purposes, role purposes, sync roles, welcome toggle, and runtime settings.
- Integrations - external service status/configuration surfaces.
- Health Status - service status and latency.

AI moderation is planned as a future module. It should not be documented as a completed Activity panel until released.

## Access Model

Activity access is not the same thing as raw Discord server roles. Discord roles are synchronized into Muxivo Discord and then mapped to Activity access roles.

Built-in Activity roles:

- `creator`;
- `developer`;
- `moderator`;
- `administrator`.

Rules:

- users must open the panel from a Discord server Activity launch;
- Discord server administrators can synchronize roles with `/sync_roles` or the Activity sync action;
- if Discord roles are not synchronized, users can receive `403`;
- tabs are hidden when the user's Activity role has no permission for that module;
- administrator access should be limited to trusted users.

Creator Alerts visibility:

- administrators see all connected sources;
- creators see only their own sources;
- creators use the default stream ping role;
- administrators can override source ping role.

## Developer Portal Setup

1. Open the Discord Developer Portal for the Muxivo Discord application.
2. Enable Activities for the app.
3. Add the Activity URL Mapping that points to the public HTTPS URL serving this FastAPI app.
4. Keep the application as a confidential client for this deployment. Do not enable Public Client.
5. Use the bot invite URL scopes `bot` and `applications.commands`.

The Activity SDK authorization uses:

- `identify`;
- `guilds`;
- `applications.commands`.

## Local Run

Create `activity/client/.env`:

```env
VITE_DISCORD_CLIENT_ID=your_discord_application_client_id
VITE_API_BASE_URL=
```

Start the backend:

```bash
python -m uvicorn activity.server.main:app --host 0.0.0.0 --port 8008 --reload
```

Start the frontend:

```bash
cd activity/client
npm install
npm run dev
```

For local UI work, Vite proxies `/api` to `http://localhost:8008`. For production, leave `VITE_API_BASE_URL` empty so the built frontend calls the same origin with `/api/...`.

## Required Server Env

```env
DISCORD_CLIENT_ID=your_discord_application_client_id
DISCORD_CLIENT_SECRET=your_discord_oauth_client_secret
DISCORD_PROXY_URL=http://127.0.0.1:10809
```

Creator Alerts can also use:

```env
TWITCH_CLIENT_ID=your_twitch_client_id
TWITCH_CLIENT_SECRET=your_twitch_client_secret
YOUTUBE_API_KEY=your_youtube_api_key
```

## Production Services

The current production services are:

- `muxivo-discord-bot`;
- `muxivo-discord-activity`;
- proxy service when Discord traffic must be routed.

`muxivo-discord-bot` and `muxivo-discord-activity` should start after the proxy when Discord access depends on it.

## Frontend Safety Notes

- Treat Discord snowflake IDs as strings.
- Do not convert guild, channel, role, message, or user IDs to JavaScript `number`.
- Do not place `DISCORD_CLIENT_SECRET` in frontend code.
- Do not compile production builds with `127.0.0.1` or `localhost` as API base URL.
- Avoid horizontal overflow in panels; long URLs and IDs must wrap inside their cards.
