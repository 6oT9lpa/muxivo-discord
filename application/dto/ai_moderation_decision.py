from pydantic import BaseModel, ConfigDict, Field


class AiModerationDecision(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: int = Field(gt=0)
    user_id: int = Field(gt=0)
    guild_id: int = Field(gt=0)
    message_id: int = Field(gt=0)
    risk_score: float = Field(ge=0, le=100)
    severity: int = Field(default=0, ge=0, le=5)
    confidence: float = Field(default=0.0, ge=0, le=1)
    latency_ms: int = Field(default=0, ge=0)
    action: str = Field(min_length=1, max_length=32)
    proposed_action: str | None = Field(default=None, max_length=32)
    primary_label: str = Field(min_length=1, max_length=32)
    labels: tuple[str, ...] = Field(max_length=14)
    rule_matches: tuple[str, ...] = Field(default=(), max_length=32)
    execution_plan: tuple[str, ...] = Field(max_length=8)
    warnings: tuple[str, ...] = Field(default=(), max_length=8)
    # Core can report an unavailable duplicate alongside an attachment whose
    # OCR completed successfully. The presentation layer needs this distinction.
    media_analysis_succeeded: bool = False
    dry_run: bool
