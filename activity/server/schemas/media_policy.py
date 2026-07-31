from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MediaPolicyPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    guild_id: int = Field(gt=0)
    expected_revision: int = Field(ge=0)
    media: dict[str, Any]
