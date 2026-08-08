from datetime import datetime, timezone
import asyncio
import json
import re

import httpx

from application.dto.ai_moderation_request import AiModerationRequest
from application.dto.user_moderation_context import UserModerationContext, UserPunishmentStatistics
from infrastructure.ai.muxivo_core_api_client import AiModeratorApiClient


def test_muxivo_core_payload_serializes_discord_ids_as_strings() -> None:
    client = AiModeratorApiClient("http://127.0.0.1:8000", "key", 1)
    payload = client._moderation_payload(
        AiModerationRequest(
            guild_id=1150681470634049668,
            channel_id=1525175773722579145,
            user_id=762514681209946122,
            message_id=1525175773722579145,
            reply_to_message_id=1525175773722579144,
            raw_text="message",
            created_at=datetime.now(timezone.utc),
            mention_count=2,
        )
    )

    assert payload["platform"] == "discord"
    assert payload["guild_id"] == "1150681470634049668"
    assert payload["channel_id"] == "1525175773722579145"
    assert payload["user_id"] == "762514681209946122"
    assert payload["message_id"] == "1525175773722579145"
    assert payload["reply_to_message_id"] == "1525175773722579144"
    assert payload["mention_count"] == 2


def test_muxivo_core_payload_includes_validated_user_context() -> None:
    client = AiModeratorApiClient("http://127.0.0.1:8000", "key", 1)
    payload = client._moderation_payload(
        AiModerationRequest(
            guild_id=1,
            channel_id=2,
            user_id=3,
            message_id=4,
            raw_text="message",
            created_at=datetime.now(timezone.utc),
            event_type="UPDATE",
            user_context=UserModerationContext(
                account_age_days=100,
                guild_membership_days=10,
                punishments=UserPunishmentStatistics(window_days=30, total_in_window=2),
            ),
        )
    )
    assert payload["event_type"] == "UPDATE"
    assert payload["user_context"]["punishments"]["total_in_window"] == 2


def test_muxivo_core_payload_does_not_include_removed_author_fields() -> None:
    client = AiModeratorApiClient("http://127.0.0.1:8000", "key", 1)
    payload = client._moderation_payload(
        AiModerationRequest(
            guild_id=1,
            channel_id=2,
            user_id=3,
            message_id=4,
            raw_text="message",
            created_at=datetime.now(timezone.utc),
        )
    )

    assert "author_role_ids" not in payload
    assert "author_is_bot" not in payload


def test_moderate_forwards_safe_correlation_id() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            request=request,
            json={
                "dataset_event_id": 1, "risk_score": 0, "decision_action": "LOG",
                "primary_label": "SAFE", "labels": ["SAFE"], "execution_plan": ["LOG"],
            },
        )

    async def exercise() -> None:
        client = AiModeratorApiClient("http://muxivo-core", "internal-key", 1)
        client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            await client.moderate(
                AiModerationRequest(guild_id=1, channel_id=2, user_id=3, message_id=4, raw_text="", created_at=datetime.now(timezone.utc))
            )
        finally:
            await client.close()

    asyncio.run(exercise())
    assert re.fullmatch(r"[0-9a-f-]{36}", requests[0].headers["x-correlation-id"])


def test_media_policy_requests_forward_verified_scope_and_revision() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"source": "DATABASE", "revision": 4})

    async def exercise() -> None:
        client = AiModeratorApiClient("http://muxivo-core", "internal-key", 1)
        client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            await client.get_media_policy(123)
            await client.save_media_policy(
                guild_id=123,
                actor_id=456,
                expected_revision=3,
                media={"ocr": {"enabled": True}},
            )
            await client.reset_media_policy(guild_id=123, actor_id=456, expected_revision=4)
        finally:
            await client.close()

    asyncio.run(exercise())

    assert [request.method for request in requests] == ["GET", "PUT", "DELETE"]
    assert requests[0].url.params["guild_id"] == "123"
    assert requests[1].headers["x-verified-guild-id"] == "123"
    assert requests[1].headers["x-actor-id"] == "456"
    assert json.loads(requests[1].content) == {
        "expected_revision": 3,
        "media": {"ocr": {"enabled": True}},
    }
    assert requests[2].url.params["expected_revision"] == "4"


def test_feedback_request_uses_internal_api_and_idempotent_lineage() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"status": "accepted", "event_id": 9, "correlation_id": "cid"})

    async def exercise() -> None:
        client = AiModeratorApiClient("http://muxivo-core", "internal-key", 1)
        client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            await client.submit_feedback(
                guild_id=123,
                message_id=456,
                feedback_type="corrected",
                labels=("SCAM",),
                primary_label="SCAM",
                severity=4,
                recommended_action="KICK",
                original_action="REVIEW",
                moderator_id="a" * 64,
                idempotency_key="activity-review-123-7-1",
            )
        finally:
            await client.close()

    asyncio.run(exercise())

    assert requests[0].url.path == "/moderation/feedback"
    assert requests[0].headers["x-internal-api-key"] == "internal-key"
    payload = json.loads(requests[0].content)
    assert payload["guild_id"] == "123"
    assert payload["message_id"] == "456"
    assert payload["recommended_action"] == "KICK"
    assert payload["idempotency_key"] == "activity-review-123-7-1"
