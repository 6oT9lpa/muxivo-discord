from datetime import datetime, timezone

from core.interfaces.repositories.member_join_history_repository_interface import MemberJoinHistoryRepositoryInterface
from infrastructure.logging import get_logger

logger = get_logger(__name__)


class MemberJoinHistoryService:
    def __init__(self, repository: MemberJoinHistoryRepositoryInterface) -> None:
        self._repository = repository

    async def record_join(self, guild_id: int, user_id: int, joined_at: datetime | None) -> bool:
        if joined_at is None:
            logger.warning("Member join history skipped because joined_at is unavailable guild_id=%s user_id=%s", guild_id, user_id)
            return False
        first_join = await self._repository.record_join(guild_id, user_id, self._as_utc(joined_at))
        logger.info("Member join history recorded guild_id=%s user_id=%s join_kind=%s", guild_id, user_id, "first" if first_join else "rejoin")
        return first_join

    async def record_leave(
        self,
        guild_id: int,
        user_id: int,
        left_at: datetime | None = None,
    ) -> bool:
        occurred_at = self._as_utc(left_at or datetime.now(timezone.utc))
        recorded = await self._repository.record_leave(guild_id, user_id, occurred_at)
        logger.info(
            "Member leave history recorded guild_id=%s user_id=%s inserted=%s",
            guild_id,
            user_id,
            recorded,
        )
        return recorded

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
