from __future__ import annotations

import httpx
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from application.dto.ai_moderation_decision import AiModerationDecision
from application.dto.ai_moderation_request import AiModerationRequest
from infrastructure.logging import get_logger

logger = get_logger(__name__)


class AiModeratorApiClient:
    def __init__(self, base_url: str, api_key: str, timeout_seconds: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = httpx.Timeout(timeout_seconds)
        self._client: httpx.AsyncClient | None = None

    async def moderate(self, request: AiModerationRequest) -> AiModerationDecision:
        payload = self._moderation_payload(request)
        endpoint = "/moderation/media" if request.attachments else "/moderation/messages"
        correlation_id = str(uuid4())
        request_payload = (
            {
                "message": payload,
                "attachments": [attachment.model_dump(mode="json") for attachment in request.attachments],
            }
            if request.attachments
            else payload
        )
        response = await self._http_client().post(
            f"{self._base_url}{endpoint}",
            headers={"X-Internal-Api-Key": self._api_key, "X-Correlation-Id": correlation_id},
            json=request_payload,
        )
        if response.status_code >= 400:
            logger.warning(
                "Muxivo Core request failed status=%s message_id=%s endpoint=%s correlation_id=%s error=%s",
                response.status_code,
                request.message_id,
                endpoint,
                correlation_id,
                self._safe_error_summary(response),
            )
        response.raise_for_status()
        data = response.json()
        media_analysis_succeeded = any(
            isinstance(attachment, dict)
            and attachment.get("status") in {"analyzed", "duplicate"}
            for attachment in data.get("attachments", ())
        )
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
            warnings=tuple(
                warning
                for warning in data.get("warnings", ())
                if isinstance(warning, str)
            )[:8],
            media_analysis_succeeded=media_analysis_succeeded,
            dry_run=data.get("execution_status") == "DRY_RUN",
        )

    def _moderation_payload(self, request: AiModerationRequest) -> dict[str, Any]:
        payload = request.model_dump(
            mode="json",
            exclude={
                "author_role_ids",
                "author_is_bot",
                "attachments",
            },
        )
        payload["platform"] = "discord"
        for key in ("guild_id", "channel_id", "user_id", "message_id", "reply_to_message_id"):
            if payload.get(key) is not None:
                payload[key] = str(payload[key])
        return payload

    @staticmethod
    def _safe_error_summary(response: httpx.Response) -> tuple[tuple[str, str], ...]:
        """Return stable error metadata only; never include request or response text."""
        try:
            body = response.json()
        except (ValueError, AttributeError):
            return ()
        if not isinstance(body, dict):
            return ()
        code = body.get("code")
        if isinstance(code, str):
            return (("code", code),)
        detail = body.get("detail", ())
        if not isinstance(detail, list):
            return ()
        return tuple(
            (
                ".".join(str(part) for part in error.get("loc", ()) if part != "body"),
                str(error.get("type", "unknown")),
            )
            for error in detail
            if isinstance(error, dict)
        )

    async def report_action(self, event_id: int, action: str, status: str, dry_run: bool) -> None:
        response = await self._http_client().post(
            f"{self._base_url}/actions/result",
            headers={"X-Internal-Api-Key": self._api_key},
            json={"event_id": event_id, "action": action, "status": status, "dry_run": dry_run, "timestamp": datetime.now(timezone.utc).isoformat()},
        )
        response.raise_for_status()

    async def submit_feedback(
        self,
        *,
        guild_id: int,
        message_id: int,
        feedback_type: str,
        labels: tuple[str, ...],
        primary_label: str | None,
        severity: int,
        recommended_action: str,
        original_action: str,
        moderator_id: str,
        idempotency_key: str,
        notes: str | None = None,
    ) -> dict[str, Any]:
        response = await self._http_client().post(
            f"{self._base_url}/moderation/feedback",
            headers={
                "X-Internal-Api-Key": self._api_key,
                "X-Correlation-Id": idempotency_key,
            },
            json={
                "guild_id": str(guild_id),
                "message_id": str(message_id),
                "feedback_type": feedback_type,
                "labels": list(labels),
                "primary_label": primary_label,
                "severity": severity,
                "recommended_action": recommended_action,
                "original_action": original_action,
                "moderator_id": moderator_id,
                "annotation_source": "activity_review",
                "notes": notes,
                "idempotency_key": idempotency_key,
            },
        )
        response.raise_for_status()
        return dict(response.json())

    async def simulate(self, request: AiModerationRequest) -> dict[str, Any]:
        """Classify a dashboard test message without writing a dataset event."""
        response = await self._http_client().post(
            f"{self._base_url}/moderation/simulate",
            headers={"X-Internal-Api-Key": self._api_key},
            json=self._moderation_payload(request),
        )
        response.raise_for_status()
        return dict(response.json())

    async def get_media_policy(self, guild_id: int) -> dict[str, Any]:
        response = await self._http_client().get(
            f"{self._base_url}/policies/media",
            headers={"X-Internal-Api-Key": self._api_key},
            params={"guild_id": str(guild_id)},
        )
        response.raise_for_status()
        return dict(response.json())

    async def save_media_policy(
        self,
        *,
        guild_id: int,
        actor_id: int,
        expected_revision: int,
        media: dict[str, Any],
    ) -> dict[str, Any]:
        response = await self._http_client().put(
            f"{self._base_url}/policies/media",
            headers={
                "X-Internal-Api-Key": self._api_key,
                "X-Verified-Guild-Id": str(guild_id),
                "X-Actor-Id": str(actor_id),
            },
            json={"expected_revision": expected_revision, "media": media},
        )
        response.raise_for_status()
        return dict(response.json())

    async def reset_media_policy(self, *, guild_id: int, actor_id: int, expected_revision: int) -> dict[str, Any]:
        response = await self._http_client().delete(
            f"{self._base_url}/policies/media",
            headers={
                "X-Internal-Api-Key": self._api_key,
                "X-Verified-Guild-Id": str(guild_id),
                "X-Actor-Id": str(actor_id),
            },
            params={"expected_revision": expected_revision},
        )
        response.raise_for_status()
        return dict(response.json())

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _http_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout, trust_env=False)
        return self._client
