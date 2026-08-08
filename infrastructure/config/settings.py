from typing import Optional
from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class BotConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Discord
    discord_token: SecretStr
    discord_proxy_url: Optional[str] = None
    discord_owner_id: int = 762514681209946122

    # Database
    database_url: str

    # Logging
    log_level: str = "INFO"

    # Retention
    message_log_retention_days: int = 30
    punishment_retention_days: int = 365
    retention_cleanup_interval_hours: int = 6

    command_prefix: str = "!"
    activity_rotation_enabled: bool = True
    activity_rotation_interval_seconds: int = 600
    activity_allowed_origins: str = ""
    activity_token_exchange_limit_per_minute: int = 120
    subscription_tier: str = "free"
    creator_alert_poll_interval_seconds: int = 180

    twitch_client_id: Optional[str] = None
    twitch_client_secret: Optional[SecretStr] = None
    youtube_api_key: Optional[SecretStr] = None

    muxivo_core_api_url: str = "http://127.0.0.1:8000"
    muxivo_core_internal_api_key: Optional[SecretStr] = None
    muxivo_core_queue_size: int = 500
    muxivo_core_worker_count: int = 2
    muxivo_core_request_timeout_seconds: float = 12.0

    @field_validator('activity_rotation_interval_seconds')
    @classmethod
    def validate_activity_rotation_interval(cls, v: int) -> int:
        if v < 15:
            raise ValueError('Activity rotation interval must be at least 15 seconds')
        return v

    @field_validator('database_url')
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        if not value.startswith(("postgresql://", "postgres://")):
            raise ValueError("DATABASE_URL must use PostgreSQL")
        return value

    @field_validator("subscription_tier")
    @classmethod
    def validate_subscription_tier(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"free", "plus", "pro"}:
            raise ValueError("SUBSCRIPTION_TIER must be free, plus, or pro")
        return normalized

    @field_validator("creator_alert_poll_interval_seconds")
    @classmethod
    def validate_creator_alert_poll_interval(cls, value: int) -> int:
        if value < 30:
            raise ValueError("CREATOR_ALERT_POLL_INTERVAL_SECONDS must be at least 30 seconds")
        return value
    
