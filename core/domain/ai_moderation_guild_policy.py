from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from core.domain.ai_moderation_action import AiModerationAction
from core.domain.ai_moderation_label_policy import AiModerationLabelPolicy
from core.domain.ai_moderation_enforcement_mode import AiModerationEnforcementMode


class AiModerationGuildPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    blacklist_words: tuple[str, ...] = Field(default=(), max_length=200)
    allowed_domains: tuple[str, ...] = Field(default=(), max_length=200)
    labels: dict[str, AiModerationLabelPolicy] = Field(default_factory=dict, max_length=32)
    blacklist_action: AiModerationAction = AiModerationAction.DELETE_WARN
    unapproved_domain_action: AiModerationAction = AiModerationAction.REVIEW
    context_window_days: int = Field(default=30, ge=1, le=3650)
    repeat_offender_threshold: int = Field(default=3, ge=1, le=1000)
    repeat_offender_action: AiModerationAction = AiModerationAction.TIMEOUT
    escalation_enabled: bool = True
    escalation_score_threshold: float = Field(default=3.0, ge=0.1, le=1000)
    escalation_half_life_days: float = Field(default=30.0, ge=1.0, le=3650)
    excluded_user_ids: tuple[int, ...] = Field(default=(), max_length=500)
    excluded_role_ids: tuple[int, ...] = Field(default=(), max_length=500)
    excluded_channel_ids: tuple[int, ...] = Field(default=(), max_length=500)
    exclude_bots: bool = True
    # Image and GIF analysis is opt-in per guild.  Keeping it disabled by
    # default preserves the historical text-only moderation behaviour until an
    # administrator explicitly enables OCR in AI Moderator settings.
    ocr_enabled: bool = False
    ocr_failure_mode: Literal["SKIP", "REVIEW"] = "SKIP"
    ocr_max_gif_frames: int = Field(default=6, ge=1, le=24)
    ocr_process_empty_result: bool = False
    test_mode: bool = False
    enforcement_mode: AiModerationEnforcementMode = AiModerationEnforcementMode.SHADOW
    limited_min_confidence: float = Field(default=0.95, ge=0.0, le=1.0)
    limited_hard_rule_labels: tuple[str, ...] = ("INVITE", "SCAM")
    beta_enforcement_acknowledged: bool = False
    allow_automated_timeout: bool = False
    allow_automated_kick: bool = False
    allow_automated_ban: bool = False

    @field_validator("limited_hard_rule_labels")
    @classmethod
    def normalize_hard_rule_labels(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(dict.fromkeys(value.strip().upper() for value in values if value.strip()))
        if not normalized:
            raise ValueError("limited_hard_rule_labels must not be empty")
        return normalized

    @model_validator(mode="after")
    def validate_elevated_actions(self) -> "AiModerationGuildPolicy":
        """Validate execution switches without rejecting safe recommendations.

        Label action bounds are recommendations used by the decision engine. In
        Shadow and Limited modes those bounds must be retained for review and
        analytics, even if they mention a high-impact action. The policy
        enforcer, rather than schema loading, prevents their execution.
        """
        required_switches = {
            AiModerationAction.TIMEOUT: self.allow_automated_timeout,
            AiModerationAction.KICK: self.allow_automated_kick,
            AiModerationAction.BAN: self.allow_automated_ban,
        }
        # The switches are meaningful only for Elevated mode. A high action in
        # a label remains safe outside that mode because it is capped later by
        # AiModerationPolicyEnforcer before Discord actions are attempted.
        if self.enforcement_mode == AiModerationEnforcementMode.ELEVATED and not self.beta_enforcement_acknowledged:
            if any(required_switches.values()):
                raise ValueError("Elevated execution switches require beta acknowledgement")
        return self

    @field_validator("blacklist_words", "allowed_domains")
    @classmethod
    def normalize_values(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(dict.fromkeys(value.strip().casefold() for value in values if value.strip()))
        if any(len(value) > 253 for value in normalized):
            raise ValueError("policy value exceeds maximum length")
        return normalized

    @field_validator("excluded_user_ids", "excluded_role_ids", "excluded_channel_ids")
    @classmethod
    def normalize_snowflakes(cls, values: tuple[int, ...]) -> tuple[int, ...]:
        normalized = tuple(dict.fromkeys(int(value) for value in values))
        if any(value <= 0 for value in normalized):
            raise ValueError("excluded IDs must be positive Discord snowflakes")
        return normalized

    @field_validator("labels", mode="before")
    @classmethod
    def normalize_labels(cls, values: Mapping[str, object]) -> dict[str, object]:
        if not isinstance(values, Mapping):
            raise ValueError("labels must be an object")
        return {str(label).strip().upper(): value for label, value in values.items() if str(label).strip()}
