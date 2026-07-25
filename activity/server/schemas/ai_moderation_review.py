"""Strict payloads for moderator corrections in the AI review queue."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from core.domain.ai_moderation_action import AiModerationAction


class AiModerationReviewUpdatePayload(BaseModel):
    """Only explicitly editable review fields may cross the Activity boundary."""

    model_config = ConfigDict(extra="forbid")

    guild_id: int = Field(gt=0)
    revision: int = Field(ge=1)
    message_text: str = Field(min_length=1, max_length=8000)
    risk_score: float = Field(ge=0, le=100)
    severity: int = Field(ge=0, le=5)
    action: AiModerationAction
    status: Literal["OPEN", "RESOLVED"]
