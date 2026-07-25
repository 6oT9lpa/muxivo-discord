from abc import ABC, abstractmethod
from typing import Mapping
from datetime import datetime


class AiModerationRepositoryInterface(ABC):
    @abstractmethod
    async def add_channel(self, guild_id: int, channel_id: int) -> None: ...

    @abstractmethod
    async def remove_channel(self, guild_id: int, channel_id: int) -> bool: ...

    @abstractmethod
    async def list_channels(self, guild_id: int) -> list[int]: ...

    @abstractmethod
    async def get_policy(self, guild_id: int) -> dict[str, object]: ...

    @abstractmethod
    async def save_policy(self, guild_id: int, policy: Mapping[str, object]) -> None: ...

    @abstractmethod
    async def save_event(self, guild_id: int, channel_id: int, message_id: int, user_id: int, risk_score: float, action: str, proposed_action: str | None, primary_label: str, labels: tuple[str, ...], confidence: float, latency_ms: int, status: str) -> None: ...

    @abstractmethod
    async def create_review_item(self, guild_id: int, channel_id: int, message_id: int, user_id: int, message_text: str, risk_score: float, severity: int, action: str, labels: tuple[str, ...]) -> None: ...

    @abstractmethod
    async def count_ai_deleted_messages(self, guild_id: int, user_id: int, since: datetime) -> int: ...

    @abstractmethod
    async def schedule_role_restoration(self, guild_id: int, user_id: int, role_ids: tuple[int, ...], restore_at: datetime) -> None: ...

    @abstractmethod
    async def list_due_role_restorations(self) -> list[dict[str, object]]: ...

    @abstractmethod
    async def mark_roles_restored(self, guild_id: int, user_id: int) -> None: ...
