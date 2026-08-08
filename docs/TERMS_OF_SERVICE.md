# Terms of Service for Muxivo Discord

**Effective Date:** June 18, 2026  
**Last Updated:** August 08, 2026

These Terms of Service govern use of Muxivo Discord, including the Discord bot, slash commands, Muxivo DS Activity control panel, Creator Alerts, Dev Blog, logging, statistics, voice rooms, role tools, welcome tools, moderation commands, and AI moderation features.

By adding Muxivo Discord to a server, using its commands, or opening the Activity panel, you agree to these Terms, the [Privacy Policy](./PRIVACY_POLICY.md), and Discord's applicable terms and policies.

## 1. Service Description

Muxivo Discord currently provides:

- Muxivo DS Activity control panel;
- Activity RBAC and role synchronization;
- autoroles and role panels;
- welcome messages;
- channel and role purpose settings;
- moderation commands and punishment history;
- logging and Activity audit events;
- server statistics and leaderboards;
- dynamic voice rooms;
- Creator Alerts for Twitch, YouTube, and Kick;
- Dev Blog drafts and publishing;
- AI moderation channel coverage, policy settings, and local Muxivo Core API integration;
- bot settings, integrations, and health surfaces.

## 2. Eligibility

Users must be allowed to use Discord under Discord rules and applicable law.

Only server owners or authorized administrators should invite Muxivo Discord, configure modules, or grant Activity permissions.

## 3. Server Administrator Responsibilities

Server administrators are responsible for:

- granting only the Discord permissions needed for selected features;
- configuring log channels so only trusted staff can access them;
- informing members when logging, statistics, moderation, Creator Alerts, or Activity audit features are enabled;
- mapping Discord roles to Activity roles carefully;
- keeping administrator Activity access limited to trusted users;
- reviewing moderation actions and punishment history;
- respecting privacy and local legal requirements;
- removing or disabling modules that the server no longer uses.

## 4. Acceptable Use

You may use Muxivo Discord to:

- manage your own Discord server;
- assign roles and operate role panels;
- publish welcome messages;
- moderate users through Discord-permitted actions;
- keep audit and moderation logs;
- collect server statistics;
- operate dynamic voice rooms;
- publish Creator Alerts for channels you are allowed to promote;
- publish Dev Blog content you are allowed to publish;
- manage server settings through the Activity panel.
- configure AI moderation for channels where you have authority to moderate.

## 5. Prohibited Use

You may not use Muxivo Discord to:

- violate Discord terms, community guidelines, or law;
- harass, stalk, threaten, or discriminate against users;
- publish private logs or personal data without a lawful basis;
- collect or sell personal data;
- run spam, raids, phishing, malware, or fraud;
- bypass Discord permissions or Activity RBAC checks;
- attempt to access bot tokens, API keys, database credentials, logs, or server infrastructure;
- publish illegal content through Dev Blog, Creator Alerts, embeds, or role panels;
- impersonate creators or publish alerts for channels you do not control or have permission to promote.
- use AI moderation outputs as a pretext for harassment, discrimination, or abusive enforcement.

We may restrict or terminate access if usage creates legal, security, privacy, or operational risk.

## 6. Moderation Commands

Muxivo Discord may help moderators warn, mute, unmute, kick, ban, unban, purge messages, configure slowmode, and review punishment history.

The user running the command and the server administration that granted permission are responsible for the action. Muxivo Discord does not define server rules and does not replace human judgment.

## 7. Logs and Audit

Logs may contain Discord IDs, usernames, message content, moderation reasons, Activity changes, and other server events.

Server administrators must keep log channels and Activity log access restricted. Logs must not be used for harassment, doxxing, blackmail, or unrelated surveillance.

## 8. Muxivo DS Activity Access

The protected Activity workspace is intended to run inside Discord.

Access is based on:

- Discord OAuth session;
- guild membership;
- synchronized Discord roles;
- Activity role mappings;
- per-module permissions.

If roles are not synchronized or permissions are missing, Muxivo Discord may deny access.

## 9. Creator Alerts

Creator Alerts may publish Twitch, YouTube, and Kick announcements.

Users are responsible for:

- connecting only sources they own or have permission to promote;
- using accurate channel URLs;
- avoiding misleading templates;
- respecting platform rules;
- respecting Discord server rules;
- not abusing ping roles.

Server administrators may see all connected sources. Creators may see only their own sources.

## 10. Dev Blog

Dev Blog is used to publish project or server updates.

Users are responsible for Dev Blog content, image URLs, titles, and embedded material. Dev Blog must not be used to publish illegal, harmful, infringing, malicious, or deceptive content.

## 11. External Services

Muxivo Discord may interact with:

- Discord API;
- Twitch;
- YouTube Data API;
- Kick endpoints;
- hosting/VPS infrastructure;
- PostgreSQL storage;
- proxy infrastructure when configured.

External services have their own terms and policies.

## 12. AI Moderation

AI moderation may classify selected-channel messages, reply context, and limited recent-message context; return labels, risk scores, confidence, and recommended actions; and assist moderators or configured policy flows.

### 12.1 Enforcement Modes and Beta Features

AI moderation has three server-controlled modes:

- **Shadow** records recommendations only and does not apply automated Discord punishment;
- **Limited** may apply low-impact actions under configured confidence and hard-rule safeguards;
- **Elevated** can apply timeout, kick, or ban only after a server administrator accepts the beta acknowledgement and explicitly enables each action.

Automated enforcement is probabilistic. It can produce false positives, false negatives, delayed actions, duplicate logs, or failed actions caused by Discord permissions, role hierarchy, unavailable channels, closed DMs, or external-service errors. Server administrators must test configuration on a test server before enabling Elevated actions on a production server.

When permitted by server policy, an enforcement plan may remove the violating message before a warning, timeout, kick, or ban. A timeout may temporarily remove only manageable administrator-permission roles required for Discord to apply the timeout; recorded eligible roles are returned after the timeout ends when they still exist and remain below the bot's highest role.

Server administrators are responsible for:

- selecting only channels that should be moderated by the AI module;
- reviewing thresholds and maximum action limits before enabling strict behavior;
- keeping Muxivo Discord's role above only the roles it is intended to manage;
- informing members when AI moderation is active;
- handling appeals, false positives, and false negatives;
- keeping human staff responsible for final server policy.

AI moderation should not be treated as a final authority. It is an assistive system and may make mistakes. Administrators, not Muxivo Discord, are responsible for their server rules, appeal process, permission setup, and decisions to enable automated enforcement.

## 13. Availability and Changes

Muxivo Discord is provided "as is" and "as available". We do not guarantee uninterrupted operation, error-free behavior, permanent availability of every module, or compatibility with every Discord configuration.

Features may change for security, stability, Discord compliance, or project development.

## 14. Limitation of Liability

To the extent permitted by law, we are not responsible for:

- moderation decisions made by server staff;
- incorrect Discord permissions;
- data loss caused by Discord, hosting, database, backup, deployment, or administrator actions;
- missed or duplicate announcements;
- failed external API calls;
- inability to use the bot or Activity panel.

Test critical features on a test server before production use.

## 15. Privacy

Data processing is described in the [Privacy Policy](./PRIVACY_POLICY.md). If you do not agree with required processing, stop using Muxivo Discord, disable the relevant module, or remove the bot from the server.

## 16. Bot Removal

A server administrator may remove Muxivo Discord at any time through Discord settings. Some stored data may remain until retention cleanup, backup expiration, or manual deletion, as described in the Privacy Policy.

## 17. Changes to These Terms

These Terms may be updated when features, infrastructure, laws, or Discord requirements change. Continued use after an update means acceptance of the updated Terms.

## 18. Contact

Questions, complaints, data deletion requests, and security reports: **https://discord.gg/6o9lpa-hub**.

Include the server ID, user ID, and a short description of the issue where relevant.
