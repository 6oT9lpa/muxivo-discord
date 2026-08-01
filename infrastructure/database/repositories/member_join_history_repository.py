from datetime import datetime

from core.interfaces.repositories.member_join_history_repository_interface import MemberJoinHistoryRepositoryInterface
from infrastructure.database.repositories.base import BaseRepository


class MemberJoinHistoryRepository(BaseRepository, MemberJoinHistoryRepositoryInterface):
    async def record_join(self, guild_id: int, user_id: int, joined_at: datetime) -> bool:
        existing = await self.fetch_one(
            "SELECT first_joined_at FROM member_join_history WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )
        await self.execute_write(
            """
            INSERT INTO member_join_history (guild_id, user_id, first_joined_at, latest_joined_at, join_count)
            VALUES (?, ?, ?, ?, 1)
            ON CONFLICT (guild_id, user_id) DO UPDATE SET
                latest_joined_at = excluded.latest_joined_at,
                join_count = member_join_history.join_count + 1
            WHERE member_join_history.latest_joined_at <> excluded.latest_joined_at
            """,
            (guild_id, user_id, joined_at, joined_at),
        )
        await self._record_lifecycle_event(guild_id, user_id, "member_join", joined_at)
        return existing is None

    async def record_leave(self, guild_id: int, user_id: int, left_at: datetime) -> bool:
        return await self._record_lifecycle_event(guild_id, user_id, "member_leave", left_at)

    async def _record_lifecycle_event(
        self,
        guild_id: int,
        user_id: int,
        event_type: str,
        occurred_at: datetime,
    ) -> bool:
        await self.execute_write(
            "DELETE FROM member_lifecycle_events WHERE retention_until <= CURRENT_TIMESTAMP"
        )
        result = await self.execute_write(
            """
            INSERT INTO member_lifecycle_events (
                guild_id, user_id, event_type, occurred_at, retention_until
            ) VALUES (?, ?, ?, ?, ? + INTERVAL '365 days')
            ON CONFLICT (guild_id, user_id, event_type, occurred_at) DO NOTHING
            """,
            (guild_id, user_id, event_type, occurred_at, occurred_at),
        )
        return bool(result.rowcount)
