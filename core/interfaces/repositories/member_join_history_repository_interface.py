from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime


class MemberJoinHistoryRepositoryInterface(ABC):
    @abstractmethod
    async def record_join(self, guild_id: int, user_id: int, joined_at: datetime) -> bool:
        """Store a join and return whether it is the member's first recorded join."""
        raise NotImplementedError

    @abstractmethod
    async def record_leave(self, guild_id: int, user_id: int, left_at: datetime) -> bool:
        """Store a deduplicated leave event for aggregate statistics."""
        raise NotImplementedError
