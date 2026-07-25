"""Safe, bounded payload for an Activity AI moderation simulation."""

from pydantic import BaseModel, ConfigDict, Field


class AiModerationSimulationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    guild_id: int = Field(gt=0)
    message_text: str = Field(min_length=1, max_length=8000)
