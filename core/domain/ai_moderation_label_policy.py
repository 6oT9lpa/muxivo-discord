from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.domain.ai_moderation_action import AiModerationAction


class AiModerationLabelPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    risk_threshold: float = Field(default=0, ge=0, le=100)
    min_action: AiModerationAction = AiModerationAction.LOG
    max_action: AiModerationAction = AiModerationAction.BAN

    @model_validator(mode="after")
    def validate_action_range(self) -> "AiModerationLabelPolicy":
        action_rank = {
            AiModerationAction.IGNORE: 0,
            AiModerationAction.LOG: 1,
            AiModerationAction.REVIEW: 2,
            AiModerationAction.WARN: 3,
            AiModerationAction.DELETE: 4,
            AiModerationAction.DELETE_WARN: 5,
            AiModerationAction.TIMEOUT: 6,
            AiModerationAction.KICK: 7,
            AiModerationAction.BAN: 8,
        }
        if action_rank[self.min_action] > action_rank[self.max_action]:
            raise ValueError("min_action must not be more severe than max_action")
        return self
