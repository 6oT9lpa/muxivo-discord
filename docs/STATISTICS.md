# Activity statistics contract

All persisted event timestamps are UTC. The API aggregates in UTC; presentation may localize timestamps but must not move events between stored UTC windows. Every query is isolated by `guild_id`. Membership lifecycle rows are retained for 365 days and expired rows are excluded and opportunistically purged.

| Metric / API field | Definition and formula | Source / grain | Period | Activity UI | Expected lag |
|---|---|---|---|---|---|
| `current_member_count` | Current Discord approximate member count; not a sum of joins | Discord guild snapshot / guild | Current | Server Stats summary | One request |
| `joins`, `leaves` | Count of deduplicated `member_join` / `member_leave` events | `member_lifecycle_events` / event | Selected 1–90 day window | Server Stats summary | Event-handler latency |
| `joins_24h`, `joins_7d`, `joins_30d` and leave equivalents | Lifecycle event counts in fixed rolling windows | `member_lifecycle_events` / event | 24h, 7d, 30d | API payload | Event-handler latency |
| `net_member_growth` | `joins - leaves` in the selected window | Derived / guild-window | Selected window | Server Stats summary | Event-handler latency |
| `membership_history_since` | Earliest retained lifecycle event. Earlier history is unknown and is never backfilled or estimated | `member_lifecycle_events` / guild | Retained history | Server Stats notice | Event-handler latency |
| `total_messages` | Non-deleted message events | `messages` / message | Selected window | Server Stats summary | Collector latency |
| `active_users`, `dau`, `wau`, `mau` | Distinct message authors in selected, 1d, 7d and 30d windows | `messages` / user-window | Rolling UTC windows | Summary/API | Collector latency |
| `messages_per_active_user` | `total_messages / active_users`, or 0 when no active users | Derived / guild-window | Selected window | API payload | Collector latency |
| `active_channels` | Distinct channels with a non-deleted message | `messages` / channel-window | Selected window | Server Stats summary | Collector latency |
| `voice_total_voice_minutes`, `voice_voice_users` | Cumulative stored voice minutes and distinct users with positive cumulative time; these fields are deliberately not labeled as period metrics | `user_stats` / user | Cumulative | Server Stats summary | Voice-session close |
| `moderation_events` | AI moderation decisions created in the selected window | `ai_moderation_events` / event | Selected window | Server Stats summary | Moderation pipeline latency |

Channel, hourly and daily series use the same selected UTC message window. User search is capped at 10 Discord matches and loads statistics with five batched aggregate queries, avoiding per-user N+1 reads. User cumulative fields (`messages_count`, `voice_minutes`) remain distinct from rolling fields (`messages_7d`, `messages_30d`, `active_days_30d`).
