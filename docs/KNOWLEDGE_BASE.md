# Muxivo Discord Knowledge Base

**Last Updated:** August 8, 2026

This knowledge base explains the current Muxivo Discord modules, how to configure them, and how to troubleshoot common problems.

## 1. What Muxivo Discord Does

Muxivo Discord manages Discord server operations through slash commands and a Muxivo DS Activity control panel.

Current ready modules:

- Muxivo DS Activity dashboard and RBAC;
- role synchronization, autoroles, and role panels;
- welcome messages and member event logs;
- channel and role purpose settings;
- moderation commands and punishment history;
- message, member, channel, moderation, and Activity audit logs;
- server statistics and leaderboards;
- dynamic voice rooms;
- Creator Alerts for Twitch, YouTube, and Kick;
- Dev Blog drafts and Components V2 publishing;
- AI moderation through the local Muxivo Core API;
- integrations and health surfaces.

## 2. Muxivo DS Activity Panel

The Activity panel is the main admin workspace. It is intended to run inside Discord.

Current panels:

- Dashboard;
- Access Control;
- Role Panels;
- Welcome Alerts;
- Creator Alerts;
- Dev Blog;
- Bot Settings;
- Logs;
- Server Stats;
- Voice Rooms;
- Muxivo Core;
- Integrations;
- Health Status.

Access rules:

- Discord server administrators can synchronize roles.
- Synchronized Discord roles are mapped to Activity roles.
- Activity roles decide which tabs a user can see.
- Administrators have full access.
- Creators can work with Creator Alerts.
- Developers can work with Dev Blog.
- Moderators can work with moderation-related surfaces.

Setup flow:

```text
1. Invite the bot with bot + applications.commands scopes.
2. Open the Activity from a Discord server.
3. Run /sync_roles or press Sync roles.
4. Open Access Control and configure module permissions.
5. Open Role Panels and map Discord roles to Activity roles.
6. Configure Bot Settings channel and role purposes.
```

## 3. Bot Settings

Bot Settings centralizes setup values.

Channel purposes:

- welcome;
- member log;
- moderation log;
- message log;
- channel log;
- stream announcements;
- Dev Blog.

Role purposes:

- Activity admin;
- Activity creator;
- Activity developer;
- stream ping;
- Dev Blog ping.

Useful commands:

```text
/set_channel
/list_channels
/set_role
/activity_role
/sync_roles
```

## 4. Roles and Role Panels

Ready features:

- synchronize Discord roles;
- configure autorole;
- mark roles public or hidden;
- create role panels;
- add or remove roles from panels;
- use button or reaction modes;
- map Discord roles to Activity access roles.

Useful commands:

```text
/sync_roles
/set_auto_role
/list_roles
/set_role_public
/create_panel
/panel_add
/panel_remove
/panel_list
/delete_panel
```

Troubleshooting:

- The bot role must be higher than managed roles.
- Managed integration roles cannot be assigned.
- Run `/sync_roles` after changing Discord roles.
- Reopen the Activity if the iframe still shows old role data.

## 5. Welcome Alerts

Welcome Alerts can send configured embed messages when members join.

Ready features:

- title, description, color;
- thumbnail/media settings;
- rules and roles channel buttons;
- preview;
- enable/disable;
- reset.

Useful commands:

```text
/welcome setup
/welcome media
/welcome channels
/welcome toggle
/welcome preview
/welcome reset
/welcome show
```

## 6. Creator Alerts

Creator Alerts publishes stream and content announcements for creators.

Supported platforms:

- Twitch;
- YouTube;
- Kick.

Ready features:

- up to 5 saved sources per creator;
- admins see all sources;
- creators see only their own sources;
- default stream ping role from Bot Settings;
- creators use the default ping role;
- admins can override ping role;
- custom title and description templates;
- preview test in Activity;
- platform-specific default embed copy;
- link button with configurable `Button label`;
- role pings are wrapped as spoilers;
- fallback announcements can use Discord Streaming presence if platform API credentials are missing.

Useful commands:

```text
/streamer add
/streamer remove
/streamer list
/stream-template set
```

Activity workflow:

```text
Activity -> Creator Alerts -> choose platform -> set URL -> preview -> save
```

Template variables:

```text
{creator.name}
{creator.ping}
{platform}
{url}
{game}
{title}
```

`external_channel_id`:

- Twitch: login without `@`;
- YouTube: channel ID like `UC...`;
- Kick: leave empty unless a future integration requires it;
- leave empty when the platform URL is enough.

If a YouTube stream is announced as Twitch, update to the latest build and create/preview the source again. The current build detects platform from source and URL.

## 7. Dev Blog

Dev Blog publishes project updates from the Activity panel.

Ready features:

- save drafts;
- publish directly to the configured Dev Blog channel;
- Components V2 payloads;
- up to 10 embeds/images;
- gallery-bottom mode;
- inline image-between-text mode;
- default Dev Blog ping role from Bot Settings;
- Dev Blog ping is sent as a spoiler component before the post body.

Workflow:

```text
Activity -> Dev Blog -> compose -> Save Draft
Activity -> Dev Blog -> compose -> Publish
```

Troubleshooting:

- Configure the Dev Blog channel in Bot Settings.
- Configure `ping_dev` if the post should ping a role.
- Use valid image URLs.
- If Discord rejects the message, check Activity logs for the Discord API error payload.

## 8. Moderation Commands

Ready commands:

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

Moderation actions are logged and stored for history review. The bot does not define server rules; administrators and moderators are responsible for enforcement decisions.

## 9. Logs and Audit

Muxivo Discord can log:

- message events;
- deleted and edited messages;
- member joins and leaves;
- role and channel changes;
- moderation actions;
- Activity RBAC changes;
- Dev Blog publishing;
- Creator Alert changes;
- service health and errors.

Recommended setup:

- keep log channels private;
- configure retention;
- do not expose logs publicly;
- use Activity Logs for admin audit review.

## 10. Statistics

Ready commands:

```text
/stats server
/stats user
/stats channels
/stats activity
/leaderboard
```

Activity Server Stats also exposes server metrics in the Activity panel.

## 11. Dynamic Voice Rooms

Ready features:

- trigger channel setup;
- temporary room creation;
- owner control panel;
- rename;
- user limit;
- lock/unlock;
- invite/kick;
- transfer ownership;
- cleanup empty temporary rooms.

Useful commands:

```text
/send
/voice set_trigger
/voice remove_trigger
```

## 12. AI Moderation

AI Moderation is available through the Activity panel and the local Muxivo Core API.

Current behavior:

- admins choose which Discord text/news channels are covered;
- channel IDs are validated and non-message channels are ignored;
- messages from covered channels are sent to the local Muxivo Core endpoint;
- the AI service returns labels, risk score, explanation, and recommended action;
- server policy controls thresholds, blacklist words, allowed domains, and maximum action levels;
- Activity Health shows whether the Muxivo Core API is reachable;
- the 30 July 2026 Muxivo Core release uses a separately deployed calibrated
  ruBERT Tiny2 model bundle; Muxivo Discord never stores model weights or downloads
  image bytes;
- `SHADOW` logs a proposal only, while stronger Discord actions remain subject
  to the guild's enforcement mode, permissions, and action limits.

Recommended setup:

```text
1. Start muxivo-core on the server.
2. Configure MUXIVO_CORE_API_URL and MUXIVO_CORE_INTERNAL_API_KEY in Muxivo Discord .env.
3. Open Activity -> Muxivo Core.
4. Select moderated channels.
5. Review blacklist words, allowed domains, label thresholds, and action limits.
6. Check Activity -> Health Status.
```

The Muxivo Core should assist staff, not replace human review. Use stricter automatic actions only after testing on your server.

## 13. Common Issues

### Slash Commands Do Not Appear

Check:

- the bot is online;
- `applications.commands` scope was used during invite;
- global command sync completed;
- bot has channel permissions;
- the cog loaded without errors.

### Activity Shows 403

Check:

- roles were synchronized;
- user has a Discord role mapped to an Activity role;
- target tab permission is not disabled;
- the Activity was opened from the correct Discord server.

### Creator Alerts Do Not Publish

Check:

- `stream_announce` channel purpose is configured;
- `ping_stream` role purpose is configured if pings are needed;
- source is active;
- platform credentials are configured for API monitoring, or Discord presence fallback is available;
- Presence Intent is enabled if fallback from Discord status is required.

### YouTube API Does Not Work

Check:

- `YOUTUBE_API_KEY` is present in server `.env`;
- YouTube Data API v3 is enabled for the Google Cloud project;
- the key is restricted to YouTube Data API v3;
- API quota is not exhausted.

### Twitch API Does Not Work

Check:

- `TWITCH_CLIENT_ID` and `TWITCH_CLIENT_SECRET` are present;
- Twitch app is created;
- credentials are correct;
- fallback from Discord Streaming status can still publish basic stream alerts without Twitch API.

### Dev Blog Fails With Components V2 Error

Do not send legacy `content` with Components V2 container payloads. Current Dev Blog sends role ping as a Components V2 text component and keeps post content inside the container.

### Horizontal Scroll Appears In Activity

Use the latest Activity build. Current Creator Alerts cards and preview wrap long URLs and IDs.

## 14. Data and Privacy

See:

- [Privacy Policy](./PRIVACY_POLICY.md)
- [Terms of Service](./TERMS_OF_SERVICE.md)
- [Commercial License](../COMMERCIAL_LICENSE.md)

For deletion or privacy requests, include:

- Discord user ID;
- server ID;
- what data should be exported, corrected, deleted, or disabled.

## 15. Useful Links

- [Project README](../README.md)
- [Discord Terms](https://discord.com/terms)
- [Discord Privacy Policy](https://discord.com/privacy)
