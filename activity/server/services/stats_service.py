from datetime import datetime
from typing import Any

from activity.server.dependencies import get_db
from activity.server.services.access_service import ActivityAccessService
from activity.server.services.discord_service import DiscordService
from infrastructure.logging import get_logger


logger = get_logger(__name__)


class ActivityStatsService:
    def __init__(self) -> None:
        self._access_service = ActivityAccessService()
        self._discord = DiscordService()

    async def get_server_stats(
        self, guild_id: int, period: int, access_token: str
    ) -> dict[str, Any]:
        logger.info(
            "Loading Activity server stats guild_id=%s period=%s", guild_id, period
        )
        await self._access_service.ensure_module_access(
            access_token, str(guild_id), "server-stats"
        )
        return await self.get_server_stats_snapshot(guild_id, period)

    async def get_server_stats_snapshot(
        self, guild_id: int, period: int
    ) -> dict[str, Any]:
        """Return the shared read-only server stats snapshot after boundary auth."""
        return {
            "summary": await self._query_server_stats(guild_id, period),
            "channels": await self._query_channel_stats(guild_id, period),
            "hourly": await self._query_hourly_stats(guild_id, period),
            "daily": await self._query_daily_stats(guild_id, min(period, 30)),
        }

    async def search_user_stats(
        self, guild_id: int, query: str, access_token: str
    ) -> list[dict[str, Any]]:
        logger.info("Searching Activity user stats guild_id=%s query=%s", guild_id, query)
        await self._access_service.ensure_module_access(
            access_token, str(guild_id), "server-stats"
        )
        # Discord's member-search endpoint only matches display names. It does
        # not find a snowflake (or a fragment of it), which made a valid ID
        # search look like an empty result in the Activity.
        normalized_query = query.strip().casefold()
        if normalized_query.isdigit():
            members = [
                member
                for member in await self._discord.list_members(str(guild_id), 1000)
                if normalized_query in str(member.id)
            ][:10]
        else:
            members = await self._discord.search_members(str(guild_id), query, 10)
        member_ids = [int(member.id) for member in members]
        stats_by_user = await self._query_user_stats_batch(guild_id, member_ids)
        return [
            {
                "member": member.model_dump(),
                "stats": stats_by_user.get(
                    int(member.id),
                    self._empty_user_stats(guild_id, int(member.id)),
                ),
            }
            for member in members
        ]

    def _empty_user_stats(self, guild_id: int, user_id: int) -> dict[str, Any]:
        return {
            "user_id": user_id,
            "guild_id": guild_id,
            "messages_count": 0,
            "voice_minutes": 0,
            "warnings_count": 0,
            "last_message": None,
            "joined_at": None,
            "first_joined_at": None,
            "latest_joined_at": None,
            "join_count": 0,
            "messages_7d": 0,
            "messages_30d": 0,
            "active_days_30d": 0,
            "timeouts_count": 0,
            "kicks_count": 0,
            "bans_count": 0,
            "ai_flags": 0,
            "moderator_overrides": 0,
        }

    async def _query_user_stats_batch(
        self,
        guild_id: int,
        user_ids: list[int],
    ) -> dict[int, dict[str, Any]]:
        if not user_ids:
            return {}
        params = (guild_id, user_ids)
        base_rows = await self._fetch_all_or_empty(
            "SELECT * FROM user_stats WHERE guild_id = ? AND user_id = ANY(?::bigint[])",
            params,
            "user cumulative stats",
        )
        activity_rows = await self._fetch_all_or_empty(
            """
            SELECT user_id,
                   COUNT(*) FILTER (WHERE timestamp >= CURRENT_TIMESTAMP - INTERVAL '7 days') AS messages_7d,
                   COUNT(*) FILTER (WHERE timestamp >= CURRENT_TIMESTAMP - INTERVAL '30 days') AS messages_30d,
                   COUNT(DISTINCT timestamp::date) FILTER (WHERE timestamp >= CURRENT_TIMESTAMP - INTERVAL '30 days') AS active_days_30d
            FROM messages
            WHERE guild_id = ? AND user_id = ANY(?::bigint[]) AND deleted = 0
            GROUP BY user_id
            """,
            params,
            "user period stats",
        )
        join_rows = await self._fetch_all_or_empty(
            """
            SELECT user_id, first_joined_at, latest_joined_at, join_count
            FROM member_join_history
            WHERE guild_id = ? AND user_id = ANY(?::bigint[])
            """,
            params,
            "user join stats",
        )
        punishment_rows = await self._fetch_all_or_empty(
            """
            SELECT user_id,
                   COUNT(*) FILTER (WHERE type = 'warn') AS warnings_count,
                   COUNT(*) FILTER (WHERE type IN ('mute', 'timeout')) AS timeouts_count,
                   COUNT(*) FILTER (WHERE type = 'kick') AS kicks_count,
                   COUNT(*) FILTER (WHERE type = 'ban') AS bans_count
            FROM punishments
            WHERE guild_id = ? AND user_id = ANY(?::bigint[])
            GROUP BY user_id
            """,
            params,
            "user moderation stats",
        )
        ai_rows = await self._fetch_all_or_empty(
            """
            SELECT event.user_id,
                   COUNT(*) AS ai_flags,
                   COUNT(label.id) FILTER (WHERE label.label <> event.primary_label AND label.status = 'ACTIVE') AS moderator_overrides
            FROM ai_moderation_events event
            LEFT JOIN manual_labels label
              ON label.guild_id = event.guild_id AND label.message_id = event.message_id
            WHERE event.guild_id = ? AND event.user_id = ANY(?::bigint[])
            GROUP BY event.user_id
            """,
            params,
            "user AI moderation stats",
        )
        result = {
            user_id: self._empty_user_stats(guild_id, user_id) for user_id in user_ids
        }
        for rows in (base_rows, activity_rows, join_rows, punishment_rows, ai_rows):
            for row in rows:
                user_id = int(row["user_id"])
                result[user_id].update(
                    {
                        key: (str(value) if isinstance(value, datetime) else value)
                        for key, value in row.items()
                    }
                )
        return result

    async def _query_server_stats(self, guild_id: int, period: int) -> dict[str, Any]:
        cutoff = f"-{period} days"
        messages = await self._fetch_one_or_empty(
            """
            SELECT COUNT(*) AS total_messages,
                   COUNT(DISTINCT user_id) AS active_users,
                   COUNT(DISTINCT channel_id) AS active_channels,
                   COUNT(DISTINCT user_id) FILTER (WHERE timestamp >= CURRENT_TIMESTAMP - INTERVAL '1 day') AS dau,
                   COUNT(DISTINCT user_id) FILTER (WHERE timestamp >= CURRENT_TIMESTAMP - INTERVAL '7 days') AS wau,
                   COUNT(DISTINCT user_id) FILTER (WHERE timestamp >= CURRENT_TIMESTAMP - INTERVAL '30 days') AS mau
            FROM messages
            WHERE guild_id = ? AND timestamp >= CURRENT_TIMESTAMP + (?::interval) AND deleted = 0
            """,
            (guild_id, cutoff),
            "server message stats",
        )
        voice = await self._fetch_one_or_empty(
            """
            SELECT COUNT(DISTINCT user_id) AS voice_users,
                   SUM(voice_minutes) AS total_voice_minutes
            FROM user_stats
            WHERE guild_id = ? AND voice_minutes > 0
            """,
            (guild_id,),
            "server voice stats",
        )
        membership = await self._fetch_one_or_empty(
            """
            SELECT
                COUNT(*) FILTER (WHERE event_type = 'member_join' AND occurred_at >= CURRENT_TIMESTAMP + (?::interval)) AS joins,
                COUNT(*) FILTER (WHERE event_type = 'member_leave' AND occurred_at >= CURRENT_TIMESTAMP + (?::interval)) AS leaves,
                COUNT(*) FILTER (WHERE event_type = 'member_join' AND occurred_at >= CURRENT_TIMESTAMP - INTERVAL '1 day') AS joins_24h,
                COUNT(*) FILTER (WHERE event_type = 'member_join' AND occurred_at >= CURRENT_TIMESTAMP - INTERVAL '7 days') AS joins_7d,
                COUNT(*) FILTER (WHERE event_type = 'member_join' AND occurred_at >= CURRENT_TIMESTAMP - INTERVAL '30 days') AS joins_30d,
                COUNT(*) FILTER (WHERE event_type = 'member_leave' AND occurred_at >= CURRENT_TIMESTAMP - INTERVAL '1 day') AS leaves_24h,
                COUNT(*) FILTER (WHERE event_type = 'member_leave' AND occurred_at >= CURRENT_TIMESTAMP - INTERVAL '7 days') AS leaves_7d,
                COUNT(*) FILTER (WHERE event_type = 'member_leave' AND occurred_at >= CURRENT_TIMESTAMP - INTERVAL '30 days') AS leaves_30d,
                MIN(occurred_at) AS membership_history_since
            FROM member_lifecycle_events
            WHERE guild_id = ? AND retention_until > CURRENT_TIMESTAMP
            """,
            (cutoff, cutoff, guild_id),
            "server join stats",
        )
        moderation = await self._fetch_one_or_empty(
            """
            SELECT COUNT(*) AS moderation_events
            FROM ai_moderation_events
            WHERE guild_id = ? AND created_at >= CURRENT_TIMESTAMP + (?::interval)
            """,
            (guild_id, cutoff),
            "server moderation stats",
        )
        guild = await self._discord.safe_bot_request(
            "GET",
            f"/guilds/{guild_id}",
            params={"with_counts": "true"},
        )
        guild_payload = guild if isinstance(guild, dict) else {}
        normalized_messages = {
            key: int(value or 0) for key, value in (messages or {}).items()
        }
        normalized_membership = {
            key: (
                str(value)
                if key == "membership_history_since" and value is not None
                else int(value or 0)
            )
            for key, value in (membership or {}).items()
        }
        joins = int(normalized_membership.get("joins", 0))
        leaves = int(normalized_membership.get("leaves", 0))
        active_users = int(normalized_messages.get("active_users", 0))
        total_messages = int(normalized_messages.get("total_messages", 0))
        return {
            **normalized_messages,
            "messages_per_active_user": (
                round(total_messages / active_users, 2) if active_users else 0
            ),
            **{f"voice_{key}": int(value or 0) for key, value in (voice or {}).items()},
            **normalized_membership,
            "net_member_growth": joins - leaves,
            "current_member_count": int(
                guild_payload.get("approximate_member_count") or 0
            ),
            "moderation_events": int((moderation or {}).get("moderation_events") or 0),
            "membership_history_complete": False,
            "period_days": period,
        }

    async def _query_channel_stats(
        self, guild_id: int, period: int
    ) -> list[dict[str, Any]]:
        rows = await self._fetch_all_or_empty(
            """
            SELECT channel_id, COUNT(*) AS messages
            FROM messages
            WHERE guild_id = ? AND timestamp >= CURRENT_TIMESTAMP + (?::interval) AND deleted = 0
            GROUP BY channel_id
            ORDER BY messages DESC
            LIMIT 100
            """,
            (guild_id, f"-{period} days"),
            "channel message stats",
        )
        channels = {
            channel["id"]: channel
            for channel in await self._discord.safe_bot_request(
                "GET", f"/guilds/{guild_id}/channels"
            )
            or []
        }
        return [
            {
                **row,
                "channel_name": channels.get(str(row["channel_id"]), {}).get(
                    "name", str(row["channel_id"])
                ),
            }
            for row in rows
        ]

    async def _query_hourly_stats(
        self, guild_id: int, period: int
    ) -> list[dict[str, int]]:
        rows = await self._fetch_all_or_empty(
            """
            SELECT EXTRACT(HOUR FROM timestamp)::integer AS hour, COUNT(*) AS count
            FROM messages
            WHERE guild_id = ? AND timestamp >= CURRENT_TIMESTAMP + (?::interval) AND deleted = 0
            GROUP BY hour
            ORDER BY hour
            """,
            (guild_id, f"-{period} days"),
            "hourly message stats",
        )
        values = {hour: 0 for hour in range(24)}
        for row in rows:
            values[int(row["hour"])] = int(row["count"])
        return [{"hour": hour, "count": count} for hour, count in values.items()]

    async def _query_daily_stats(
        self, guild_id: int, days: int
    ) -> list[dict[str, Any]]:
        rows = await self._fetch_all_or_empty(
            """
            SELECT timestamp::date AS day, COUNT(*) AS count
            FROM messages
            WHERE guild_id = ? AND timestamp >= CURRENT_TIMESTAMP + (?::interval) AND deleted = 0
            GROUP BY day
            ORDER BY day
            """,
            (guild_id, f"-{days - 1} days"),
            "daily message stats",
        )
        counts = {str(row["day"]): int(row["count"]) for row in rows}
        series = []
        for index in range(days - 1, -1, -1):
            day_row = await get_db().fetch_one(
                "SELECT (CURRENT_DATE + (?::interval))::date AS day",
                (f"-{index} days",),
            )
            day = str(day_row["day"])
            series.append({"date": day, "count": counts.get(day, 0)})
        return series

    async def _fetch_one_or_empty(
        self, query: str, params: tuple[Any, ...], label: str
    ) -> dict[str, Any]:
        try:
            return await get_db().fetch_one(query, params) or {}
        except Exception as exc:
            logger.warning("Activity %s unavailable error=%s", label, exc)
            return {}

    async def _fetch_all_or_empty(
        self, query: str, params: tuple[Any, ...], label: str
    ) -> list[dict[str, Any]]:
        try:
            return await get_db().fetch_all(query, params)
        except Exception as exc:
            logger.warning("Activity %s unavailable error=%s", label, exc)
            return []
