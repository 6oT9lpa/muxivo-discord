from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserPunishmentStatistics(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    window_days: int = Field(ge=1, le=3650)
    total_in_window: int = Field(default=0, ge=0)
    timeouts_in_window: int = Field(default=0, ge=0)
    ai_deleted_messages_in_window: int = Field(default=0, ge=0)
    bans_in_window: int = Field(default=0, ge=0)
    weighted_escalation_score: float = Field(default=0.0, ge=0.0)
    last_punishment_at: datetime | None = None


class UserModerationContext(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    account_created_at: datetime | None = None
    joined_guild_at: datetime | None = None
    account_age_days: int | None = Field(default=None, ge=0)
    guild_membership_days: int | None = Field(default=None, ge=0)
    punishments: UserPunishmentStatistics
