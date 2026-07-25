from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from application.dto.user_moderation_context import UserModerationContext



class AiModerationRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    guild_id: int = Field(gt=0)
    channel_id: int = Field(gt=0)
    user_id: int = Field(gt=0)
    author_role_ids: tuple[int, ...] = Field(default=(), max_length=250)
    author_is_bot: bool = False
    message_id: int = Field(gt=0)
    raw_text: str = Field(max_length=8_000)
    created_at: datetime
    author_created_at: datetime | None = None
    member_joined_at: datetime | None = None
    reply_to_message_id: int | None = Field(default=None, gt=0)
    mention_count: int = Field(default=0, ge=0, le=100)
    role_mention_count: int = Field(default=0, ge=0, le=100)
    channel_mention_count: int = Field(default=0, ge=0, le=100)
    has_attachments: bool = False
    attachment_count: int = Field(default=0, ge=0, le=50)
    recent_messages: tuple[str, ...] = Field(default=(), max_length=20)
    recent_message_timestamps: tuple[datetime, ...] = Field(default=(), max_length=20)
    metadata: dict[str, Any] = Field(default_factory=dict, max_length=32)
    event_type: Literal["CREATE", "UPDATE"] = "CREATE"
    user_context: UserModerationContext | None = None
