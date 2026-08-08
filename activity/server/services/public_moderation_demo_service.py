from datetime import datetime, timezone
from time import time_ns

from application.dto.ai_moderation_request import AiModerationRequest
from infrastructure.ai.muxivo_core_api_client import AiModeratorApiClient
from infrastructure.config import get_config
from infrastructure.logging import get_logger


logger = get_logger(__name__)


class PublicModerationDemoService:
    """Runs a non-destructive public request through the configured AI classifier."""

    _DEMO_GUILD_ID = 9_001_000_001
    _DEMO_CHANNEL_ID = 9_001_000_002
    _DEMO_USER_ID = 9_001_000_003

    def __init__(self, client: AiModeratorApiClient | None = None) -> None:
        self._client = client

    def _get_client(self) -> AiModeratorApiClient:
        if self._client is not None:
            return self._client
        config = get_config()
        api_key = config.muxivo_core_internal_api_key
        if api_key is None:
            logger.error("Public moderation demo is unavailable because the AI API key is not configured")
            raise RuntimeError("AI moderation demo is not configured")
        self._client = AiModeratorApiClient(
            base_url=config.muxivo_core_api_url,
            api_key=api_key.get_secret_value(),
            timeout_seconds=config.muxivo_core_request_timeout_seconds,
        )
        return self._client

    async def classify(self, message: str) -> dict[str, object]:
        """Classify a message without placing it on the Discord execution queue."""

        logger.info("Public moderation demo classification started message_length=%s", len(message))
        request = AiModerationRequest(
            guild_id=self._DEMO_GUILD_ID,
            channel_id=self._DEMO_CHANNEL_ID,
            user_id=self._DEMO_USER_ID,
            message_id=self._message_id(),
            raw_text=message,
            created_at=datetime.now(timezone.utc),
        )
        decision = await self._get_client().moderate(request)
        logger.info(
            "Public moderation demo classification completed risk_score=%s action=%s label=%s",
            decision.risk_score,
            decision.action,
            decision.primary_label,
        )
        return {
            "risk_score": decision.risk_score,
            "action": decision.action,
            "primary_label": decision.primary_label,
            "labels": list(decision.labels),
            "execution_plan": list(decision.execution_plan),
        }

    @staticmethod
    def _message_id() -> int:
        return time_ns() % 9_000_000_000_000_000_000 or 1
