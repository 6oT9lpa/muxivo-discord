# Muxivo Discord

![Muxivo logo](./docs/images/muxivo-logo.png)

Muxivo Discord is a modular Discord bot with a Muxivo DS Activity control panel. It combines server setup, role automation, welcome messages, role panels, logs, statistics, dynamic voice rooms, Creator Alerts for Twitch/YouTube/Kick, Dev Blog publishing, and Activity-based administration.

Built with Python 3.12, disnake, FastAPI, Vue 3, PostgreSQL, repository/service layers, dependency injection, and structured logging.

Muxivo Discord uses the separately deployed, self-hosted **Muxivo Core** service for AI-assisted moderation. The bot owns Discord permissions, guild policy, and final enforcement; the AI service only returns an explainable recommendation and an action proposal.

## Current Status

Ready modules:

| Module | Status | Notes |
| --- | --- | --- |
| Muxivo DS Activity | Ready | Dashboard, RBAC, Bot Settings, Health, Integrations, Logs, Stats, Voice Rooms, Welcome, Role Panels, Creator Alerts, Dev Blog |
| Roles | Ready | Sync roles, autorole, public/hidden roles, role panels with buttons/reactions |
| Welcome | Ready | Embed setup, media, rules/roles buttons, preview, toggle, reset |
| Logging | Ready | Message, member, channel, moderation, Activity audit and service logs |
| Moderation Commands | Ready | Warn, mute, unmute, kick, ban, unban, history, punishments, purge, slowmode |
| Statistics | Ready | Server, user, channel activity, hourly activity, leaderboard |
| Voice Rooms | Ready | Trigger channel, owner panel, limits, lock, invite, kick, transfer, cleanup |
| Creator Alerts | Ready | Twitch, YouTube, Kick sources; templates; preview; role ping; stream fallback from Discord status |
| Dev Blog | Ready | Components V2 posts, drafts, image galleries, dev ping role |
| Bot Settings | Ready | Channel purposes, role purposes, runtime settings, role sync |
| AI Moderation | Ready | Activity channel coverage, policy thresholds, blacklist/domain rules, local Muxivo Core API health and Discord moderation queue integration |

## Quick Start

### Requirements

| Component | Recommended |
| --- | --- |
| Python | 3.12+ |
| Node.js | 20+ for Activity client builds |
| Database | PostgreSQL 16+ |
| OS | Linux server for production |
| Discord intents | Server Members, Message Content, Presence if stream fallback is used |

### Install

```bash
git clone https://github.com/6oT9lpa/discord-muxivo-coreation-bot.git
cd discord-muxivo-coreation-bot

python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
python scripts/postgres_migrate.py
python main.py
```

### Activity Client

```bash
cd activity/client
npm install
npm run build
```

For production builds, keep `VITE_API_BASE_URL` empty so the built Activity frontend calls the same origin with `/api/...`.

## Environment

Core values:

```env
DISCORD_TOKEN=your_discord_bot_token
DISCORD_GUILD_ID=123456789012345678
DISCORD_OWNER_ID=123456789012345678
DATABASE_URL=postgresql://muxivo-discord:change_me@127.0.0.1:5432/muxivo-discord

DISCORD_CLIENT_ID=your_discord_application_client_id
DISCORD_CLIENT_SECRET=your_discord_oauth_client_secret
DISCORD_PROXY_URL=http://127.0.0.1:10809

LOG_LEVEL=INFO
MESSAGE_LOG_RETENTION_DAYS=30
PUNISHMENT_RETENTION_DAYS=365
RETENTION_CLEANUP_INTERVAL_HOURS=6
```

Creator platform values:

```env
TWITCH_CLIENT_ID=your_twitch_client_id
TWITCH_CLIENT_SECRET=your_twitch_client_secret
YOUTUBE_API_KEY=your_youtube_api_key
```

Activity client build values:

```env
VITE_DISCORD_CLIENT_ID=your_discord_application_client_id
VITE_API_BASE_URL=
```

Muxivo Core integration values:

```env
MUXIVO_CORE_API_URL=http://127.0.0.1:8000
MUXIVO_CORE_INTERNAL_API_KEY=change_me
MUXIVO_CORE_QUEUE_SIZE=500
MUXIVO_CORE_WORKER_COUNT=2
MUXIVO_CORE_REQUEST_TIMEOUT_SECONDS=12
```

AI moderation routing is attachment-aware. CREATE and UPDATE events without a
supported Discord image use `POST /moderation/messages`; events containing a
JPEG, PNG, or WebP attachment use `POST /moderation/media`. The media request is
built only from Discord attachment properties (ID, signed CDN URL, filename,
content type, byte size, width, and height) and still includes the complete text
message context. One Discord event receives one combined decision, so Test Mode,
action execution, and action-result reporting keep their existing semantics.

The bot does not download or inspect image bytes and does not infer attachments
from URLs written in message text. Download validation, OCR/image-provider
fallback, retention, and the final moderation decision remain responsibilities
of Muxivo Core.

For the 30 July 2026 production release, deploy Muxivo Core with its verified
`rubert-tiny2-trained-20260730` model bundle and configure the bot to reach
that service over the private network. Do not copy model weights into Muxivo Discord or
expose the moderator API publicly.

## Muxivo DS Activity

The Activity panel is intended to run inside Discord, not as a standalone public dashboard.

Current panels:

- Dashboard: module overview and recent Activity audit events.
- Access Control: Activity roles and module permissions.
- Activity Role Mapping (legacy route key: `role-panels`): maps synchronized Discord roles to Activity access roles. Public Discord role-panel messages are a separate bot feature.
- Welcome Alerts: welcome embed setup, media, channel buttons, preview, reset.
- Creator Alerts: saved creator sources, templates, preview, button label, ping role rules.
- Dev Blog: drafts and Components V2 publishing.
- Bot Settings: channel purposes, role purposes, sync roles, runtime values.
- Logs: message/server/audit log surfaces.
- Server Stats: activity metrics.
- Voice Rooms: room management.
- Muxivo Core: channel coverage, blacklist/domain policy, label thresholds, and action limits.
- Integrations: configured external systems.
- Health Status: service status and latency.

Access model:

- Discord server admins can synchronize Discord roles.
- Synchronized Discord roles can be mapped to Activity roles.
- Built-in Activity roles include `creator`, `developer`, `moderator`, and `administrator`.
- Tabs are hidden when the user's Activity role has no permission for that module.
- Administrators can see all Creator Alert sources; creators see only their own sources.

## Slash Commands

General:

```text
/help
/ping
```

Statistics:

```text
/stats server
/stats user
/stats channels
/stats activity
/leaderboard
```

Roles and panels:

```text
/sync_roles
/set_auto_role
/list_roles
/set_role_public
/set_role
/activity_role
/create_panel
/panel_add
/panel_remove
/panel_list
/delete_panel
```

Welcome and channel purposes:

```text
/set_channel
/list_channels
/welcome setup
/welcome media
/welcome channels
/welcome toggle
/welcome preview
/welcome reset
/welcome show
```

Moderation:

```text
/moderation
/warn
/mute
/unmute
/kick
/ban
/unban
/history
/punishments
/slowmode
/purge
```

Voice:

```text
/send
/voice set_trigger
/voice remove_trigger
```

Creator Alerts:

```text
/streamer add
/streamer remove
/streamer list
/stream-template set
```

## Creator Alerts

Creator Alerts supports Twitch, YouTube, and Kick sources.

Features:

- up to 5 sources per creator;
- admins can see all sources, creators see only their own;
- default stream ping role from Bot Settings `ping_stream`;
- creators cannot override ping role in Activity;
- admins can override ping role;
- custom title and description templates;
- `Button label` controls the link button on published alerts;
- role ping is sent as a spoiler;
- fallback announcements can be created from Discord Streaming presence when platform APIs are not configured.

Supported template placeholders:

```text
{creator.name}
{creator.ping}
{platform}
{url}
{game}
{title}
```

`external_channel_id` is optional. Use it when the URL is not enough:

- Twitch: channel login without `@`;
- YouTube: channel ID like `UC...`;
- otherwise leave it empty.

## Dev Blog

Dev Blog is managed from the Activity panel.

Features:

- save drafts;
- publish Components V2 posts;
- gallery mode or inline image mode;
- up to 10 embeds/images in one post;
- default `ping_dev` role from Bot Settings;
- dev ping is sent as a spoiler component before the Dev Blog content.

## AI Moderation

Muxivo Discord can send messages from selected Discord channels to the local Muxivo Core API. The AI service performs rule checks, local ruBERT classification, risk scoring, policy resolution, and returns a decision payload for the bot.

Current features:

- Activity tab for moderated channel coverage;
- blacklist words and allowed domain policy;
- per-label thresholds and action limits;
- Muxivo Core health signal in Activity Health;
- selected channel filtering to avoid invalid Discord channel IDs;
- context-aware requests with account age, current-guild membership time, and guild-scoped moderation history;
- persisted first/latest observed member joins and rejoin counts, plus idempotent audit-log ban and timeout history;
- Discord snowflakes are preserved as strings in Activity requests;
- local/self-hosted API support, including GPU-backed model loading when the server has NVIDIA drivers and CUDA-ready PyTorch;
- human-admin configuration remains the source of truth for destructive actions.

The Muxivo Core does not receive every server message by default. Only channels selected in Activity are covered.

### Request and enforcement lifecycle

```mermaid
sequenceDiagram
    participant D as Discord
    participant C as AiModerationCog
    participant Q as AiModerationQueue
    participant A as Muxivo Core API
    participant P as Guild policy enforcer
    participant R as Activity review/audit

    D->>C: CREATE or UPDATE event
    C->>C: Build bounded text, author and reply context
    C->>Q: Queue one idempotent moderation request
    Q->>A: /moderation/messages or /moderation/media
    A-->>Q: Labels, evidence, risk and action proposal
    Q-->>P: Moderation decision
    P->>R: Persist audit/review lineage
    alt SHADOW
        P-->>D: No member action
    else Policy permits action
        P->>D: Discord warning, deletion, timeout, kick or ban
        P->>A: Persist terminal action result
    end
```

`SHADOW` never punishes a member. `LIMITED` allows only constrained actions,
and `ELEVATED` additionally requires the explicit guild switches and beta
acknowledgement for timeout, kick, and ban. A model label alone never bypasses
these controls.

### Request and enforcement lifecycle

```mermaid
sequenceDiagram
    participant D as Discord
    participant C as AiModerationCog
    participant Q as AiModerationQueue
    participant A as Muxivo Core API
    participant P as Guild policy enforcer
    participant R as Activity review/audit

    D->>C: CREATE or UPDATE event
    C->>C: Build bounded text, author and reply context
    C->>Q: Queue one idempotent moderation request
    Q->>A: /moderation/messages or /moderation/media
    A-->>Q: Labels, evidence, risk and action proposal
    Q-->>P: Moderation decision
    P->>R: Persist audit/review lineage
    alt SHADOW
        P-->>D: No member action
    else Policy permits action
        P->>D: Discord warning, deletion, timeout, kick or ban
        P->>A: Persist terminal action result
    end
```

`SHADOW` never punishes a member. `LIMITED` allows only constrained actions,
and `ELEVATED` additionally requires the explicit guild switches and beta
acknowledgement for timeout, kick, and ban. A model label alone never bypasses
these controls.

Discord exposes `Member.joined_at` for the current membership, but not a reliable
first-ever join timestamp before the bot began collecting it. Migration
`0014_member_join_history` records the first and latest joins observed after it
is applied; older membership history cannot be reconstructed retrospectively.

## Data and Storage

Production and local development use PostgreSQL. The legacy SQLite import script is
only for a one-time transfer of existing data.

Stored data may include:

- guild, role, channel, message, and user IDs;
- welcome settings;
- role panel settings;
- Activity RBAC settings;
- Creator Alert sources and templates;
- Dev Blog drafts and publish records;
- AI moderation channel coverage and guild policy settings;
- logs, audit events, moderation history, statistics, voice room state.

Default retention:

- message logs: 30 days;
- expired punishment history: 365 days;
- cleanup interval: 6 hours.

## Deployment

Production services:

```bash
sudo systemctl enable muxivo-discord-bot muxivo-discord-activity
sudo systemctl start muxivo-discord-bot muxivo-discord-activity
sudo systemctl status muxivo-discord-bot muxivo-discord-activity
```

When Discord traffic must go through a proxy, keep `DISCORD_PROXY_URL` in `.env` and ensure the proxy service starts before `muxivo-discord-bot` and `muxivo-discord-activity`.

Release archives should exclude local secrets and runtime data:

```text
.git
venv
.venv
data
logs
.env
__pycache__
.pytest_cache
```

## Testing

```bash
python -m pytest
cd activity/client
npm run build
```

## Documentation

- [Architecture](./docs/ARCHITECTURE.md)
- [Knowledge Base](./docs/KNOWLEDGE_BASE.md)
- [Privacy Policy](./docs/PRIVACY_POLICY.md)
- [Terms of Service](./docs/TERMS_OF_SERVICE.md)
- [Commercial License](./COMMERCIAL_LICENSE.md)

## Support

Use GitHub issues or the project Discord support server for bug reports, setup help, data requests, and security reports.

Author: **6oT9lpa**
