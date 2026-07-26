from __future__ import annotations

import httpx
from datetime import datetime, timezone
from typing import Any

from application.dto.ai_moderation_decision import AiModerationDecision
from application.dto.ai_moderation_request import AiModerationRequest
from infrastructure.logging import get_logger

logger = get_logger(__name__)


class AiModeratorApiClient:
    def __init__(self, base_url: str, api_key: str, timeout_seconds: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = httpx.Timeout(timeout_seconds)

    async def moderate(self, request: AiModerationRequest) -> AiModerationDecision:
        payload = self._moderation_payload(request)
        async with httpx.AsyncClient(timeout=self._timeout, trust_env=False) as client:
            response = await client.post(
                f"{self._base_url}/moderation/messages",
                headers={"X-Internal-Api-Key": self._api_key},
                json=payload,
            )
        if response.status_code >= 400:
            logger.warning(
                "AI moderator request failed status=%s body=%s message_id=%s",
                response.status_code,
                response.text[:500],
                request.message_id,
            )
        response.raise_for_status()
        data = response.json()
        return AiModerationDecision(
            event_id=data["dataset_event_id"],
            user_id=request.user_id,
            guild_id=request.guild_id,
            message_id=request.message_id,
            risk_score=data["risk_score"],
            severity=data.get("severity", 0),
            confidence=data.get("confidence", 0.0),
            latency_ms=data.get("latency_ms", 0),
            action=data["decision_action"],
            proposed_action=data["decision_action"],
            primary_label=data["primary_label"],
            labels=tuple(data["labels"]),
            rule_matches=tuple(data.get("rule_matches", ())),
            execution_plan=tuple(data["execution_plan"]),
            dry_run=data.get("execution_status") == "DRY_RUN",
        )

    def _moderation_payload(self, request: AiModerationRequest) -> dict[str, Any]:
        payload = request.model_dump(mode="json", exclude={"author_role_ids", "author_is_bot"})
        payload["platform"] = "discord"
        for key in ("guild_id", "channel_id", "user_id", "message_id", "reply_to_message_id"):
            if payload.get(key) is not None:
                payload[key] = str(payload[key])
        return payload

    async def report_action(self, event_id: int, action: str, status: str, dry_run: bool) -> None:
        async with httpx.AsyncClient(timeout=self._timeout, trust_env=False) as client:
            response = await client.post(
                f"{self._base_url}/actions/result",
                headers={"X-Internal-Api-Key": self._api_key},
                json={"event_id": event_id, "action": action, "status": status, "dry_run": dry_run, "timestamp": datetime.now(timezone.utc).isoformat()},
            )
        response.raise_for_status()

    async def simulate(self, request: AiModerationRequest) -> dict[str, Any]:
        """Classify a dashboard test message without writing a dataset event."""
        async with httpx.AsyncClient(timeout=self._timeout, trust_env=False) as client:
            response = await client.post(
                f"{self._base_url}/moderation/simulate",
                headers={"X-Internal-Api-Key": self._api_key},
                json=self._moderation_payload(request),
            )
        response.raise_for_status()
        return dict(response.json())
