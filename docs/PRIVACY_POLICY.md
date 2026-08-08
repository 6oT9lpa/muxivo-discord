# Privacy Policy for Muxivo Discord

**Effective Date:** June 18, 2026  
**Last Updated:** August 08, 2026

This Privacy Policy explains what data Muxivo Discord processes, why it is processed, how it is stored, and how deletion or access requests can be made.

Muxivo Discord operates inside Discord servers and uses the Discord API. Use of Muxivo Discord also remains subject to the [Discord Terms of Service](https://discord.com/terms), [Discord Privacy Policy](https://discord.com/privacy), Discord Developer Terms, and Discord Developer Policy.

## 1. Controller and Contact

Bot operator: **6oT9lpa / Muxivo Dev**.
Contact: **Discord Support Server: https://discord.gg/6o9lpa-hub**.

Server administrators are also responsible for how Muxivo Discord is configured on their server: which modules are enabled, which channels receive logs, which roles can access Activity tabs, and who can view moderation or audit information.

## 2. Data Processed By Current Modules

Muxivo Discord processes only data needed for configured features.

### 2.1 Server and Configuration Data

Muxivo Discord may store:

- Discord server ID;
- configured channel IDs for welcome, logs, stream announcements, Dev Blog, and other purposes;
- configured role IDs for Activity access, stream ping, Dev Blog ping, autorole, and role panels;
- role names, colors, positions, and metadata used for Activity RBAC;
- bot runtime settings such as prefix, status, retention, and log level;
- welcome message configuration;
- role panel configuration;
- voice room trigger/channel configuration.

### 2.2 User and Member Data

Muxivo Discord may store or process:

- Discord user ID;
- username, display name, avatar URL, and role IDs where needed for embeds, audit logs, and permissions;
- Activity OAuth user profile and guild membership data while opening the Activity panel;
- moderation target and moderator IDs;
- voice room owner/admin/member IDs;
- statistics counters such as messages, voice time, warnings, joins, and leaves.

### 2.3 Message and Log Data

When logging or moderation modules are enabled, Muxivo Discord may process:

- message ID;
- author ID;
- channel ID;
- message content for logged message events;
- edited or deleted message content when available;
- timestamps;
- event type;
- moderation actions, punishment reasons, and durations.

Message logs are used for server administration, moderation review, audit, and statistics. Muxivo Discord does not intentionally read private direct messages unless a user directly interacts with the bot in DMs or Discord sends an interaction event to the bot.

### 2.4 Creator Alerts and External Platform Data

For Creator Alerts, Muxivo Discord may store:

- creator Discord user ID;
- platform: Twitch, YouTube, or Kick;
- channel URL;
- optional external channel ID;
- channel name;
- alert kind;
- embed title and description templates;
- button label;
- color;
- ping role ID;
- active/paused state;
- last announced event ID and last checked time.

Muxivo Discord may contact Twitch, YouTube, or Kick APIs/public endpoints only for configured monitoring and publication features. Those services have their own policies.

### 2.5 Dev Blog Data

For Dev Blog, Muxivo Discord may store:

- post title;
- content;
- embed descriptions, colors, and image URLs;
- draft/published status;
- channel ID and Discord message ID;
- author ID;
- payload used for publication.

### 2.6 Activity Panel Data

When a user opens the Muxivo DS Activity panel, Muxivo Discord processes:

- Discord OAuth code;
- backend-exchanged Discord access token for the current Activity session;
- Discord user profile;
- current guild ID;
- role/membership information needed for Activity access;
- Activity audit events created by admin actions.

The Discord client secret is handled only by the backend. It must not be placed in frontend code.

### 2.7 Technical Logs

Muxivo Discord writes technical logs to diagnose errors and keep services stable. Logs may contain:

- timestamp;
- module name;
- log level;
- error details;
- Discord IDs involved in the event;
- request path and status for Activity API requests.

### 2.8 AI Moderation Data

When AI moderation is enabled and channels are selected in Activity, Muxivo Discord may process and store:

- selected moderated channel IDs;
- guild AI moderation policy settings;
- blacklist words and allowed domains configured by administrators;
- Discord message ID, guild ID, channel ID, author ID, timestamp, and message text for covered channels;
- reply context when a covered message uses Discord's reply feature: referenced message ID, referenced author ID, and referenced message text;
- a bounded set of recent messages and timestamps from the same author for flood/spam detection;
- Muxivo Core request and response metadata such as labels, confidence, risk score, reason code, proposed and final decision action, execution status, and latency;
- configured policy values, including enforcement mode, action limits, confidence thresholds, blacklist words, allowed domains, and beta acknowledgement;
- moderation queue errors, health check results, and audit events needed to diagnose or appeal an action;
- limited metadata for enforcement notices, such as server ID, channel ID, action type, and message time when a Discord DM warning is sent.

For an automated timeout that requires temporary removal of administrator-permission roles, Muxivo Discord stores only the IDs of roles it removed, the user ID, server ID, and restoration time. This record is used solely to restore eligible roles after the timeout; it is not used for profiling.

The current production design uses a local/self-hosted Muxivo Core API. Messages are not sent to a commercial third-party AI API by default. The Muxivo Core may use local rules, local ruBERT model inference, policy resolution, and optional fallback components configured by the operator.

Only channels selected by administrators in Activity are covered by AI moderation. Server administrators are responsible for informing members when AI moderation is enabled.

## 3. Data We Do Not Intentionally Collect

Muxivo Discord does not intentionally collect:

- Discord passwords;
- user tokens;
- payment details;
- precise geolocation;
- biometric data;
- voice channel audio recordings;
- browser fingerprints for tracking;
- Discord client secrets in frontend code.

## 4. How Data Is Used

Data is used to:

- execute slash commands, buttons, menus, and modals;
- authorize Activity panel access;
- determine which Activity tabs a user may access;
- synchronize roles and manage role panels;
- send welcome messages;
- log server and moderation events;
- show statistics;
- operate voice rooms;
- publish Creator Alerts and Dev Blog posts;
- prevent duplicate stream announcements;
- send selected-channel messages to the local Muxivo Core API;
- evaluate reply and flood/spam context only for selected AI-moderated channels;
- apply configured AI moderation policy and staff review workflows;
- send moderation notices to the affected member by Discord DM when an action includes a warning, where Discord permits delivery;
- maintain audit trails;
- diagnose errors and improve service stability.

## 5. Data Sharing and Third Parties

We do not sell or rent user data.

Data may be processed by or visible to:

- Discord, because Muxivo Discord operates through Discord APIs;
- the hosting provider or VPS where Muxivo Discord runs;
- PostgreSQL storage configured by the operator;
- Twitch, YouTube, and Kick when Creator Alerts are configured;
- the local/self-hosted Muxivo Core service when AI moderation is enabled;
- proxy infrastructure such as VLESS/Xray when Discord traffic is routed through it;
- server administrators and moderators with access to logs or Activity panels;
- authorities when legally required.

## 6. Storage and Retention

Production and local deployments use PostgreSQL.

Default retention:

- message logs: 30 days unless changed by configuration;
- expired punishment history: 365 days unless changed by configuration;
- cleanup interval: approximately every 6 hours unless changed by configuration;
- server settings, Activity RBAC, role panels, welcome settings, Creator Alerts, and Dev Blog drafts: kept while the server uses the bot or until changed/deleted;
- AI moderation settings: kept while the server uses the module or until changed/deleted;
- AI moderation decision and execution records: retained for moderation review, dataset collection, metric calculation, and configured cleanup periods;
- temporary administrator-role restoration records: retained until roles are restored or the record is no longer actionable;
- technical logs: kept until log rotation or manual cleanup.

Some data may be retained longer where needed for security, abuse investigation, backups, legal compliance, or recovery.

## 7. Access, Correction, and Deletion

Users and server administrators may request:

- access to data associated with a user ID or server ID;
- correction of incorrect settings;
- deletion of user data;
- deletion of server data after bot removal;
- disabling modules that collect additional data.

To request this, contact the project support channel and include:

- Discord user ID;
- server ID;
- the requested action: export, correct, delete, or disable.

We may verify that the requester is the relevant user or a server administrator. Requests are usually reviewed within 30 days.

## 8. Security

Security measures include:

- keeping tokens and API keys in server `.env`;
- backend-only OAuth code exchange;
- Discord permission checks;
- Activity RBAC checks;
- database access restricted to the deployment environment;
- log rotation;
- avoiding frontend storage of secrets;
- optional proxy configuration via server environment.
- local Muxivo Core API keys stored in server `.env`;
- Muxivo Core access restricted to backend services.
- policy checks before automated timeout, kick, or ban;
- role-hierarchy checks before temporary administrator-role removal or restoration.

No system is perfectly secure. Report suspected leaks or vulnerabilities through the contact channel.

## 9. Children and Minimum Age

Muxivo Discord is not intended for users below the minimum age required by Discord and local law.

## 10. Changes

This policy may be updated when features, infrastructure, laws, or Discord requirements change. Material updates will be reflected by the Last Updated date.

## 11. Contact

Privacy, deletion, and security questions: **https://discord.gg/6o9lpa-hub**.

Include the server ID and user ID where relevant.
