from datetime import datetime, timezone
import json
from types import SimpleNamespace

import httpx
import pytest
from pydantic import ValidationError

from application.dto.ai_moderation_request import AiModerationRequest
from application.dto.media_attachment_request import MediaAttachmentRequest
from infrastructure.ai.muxivo_core_api_client import AiModeratorApiClient
from presentation.cogs.ai_moderation_cog import AiModerationCog


def _attachment() -> MediaAttachmentRequest:
    return MediaAttachmentRequest(
        attachment_id="10",
        download_url="https://cdn.discordapp.com/attachments/1/2/image.png",
        file_name="image.png",
        content_type="image/png",
        file_size=100,
        width=10,
        height=10,
    )


def _request(*, attachments: tuple[MediaAttachmentRequest, ...] = ()) -> AiModerationRequest:
    return AiModerationRequest(
        guild_id=1,
        channel_id=2,
        user_id=3,
        message_id=4,
        raw_text="https://attacker.example/not-an-attachment.png",
        created_at=datetime.now(timezone.utc),
        has_attachments=bool(attachments),
        attachment_count=len(attachments),
        attachments=attachments,
    )


def test_media_dto_requires_exactly_one_https_source() -> None:
    with pytest.raises(ValidationError):
        MediaAttachmentRequest(
            attachment_id="10",
            content_type="image/png",
            file_size=100,
        )
    with pytest.raises(ValidationError):
        MediaAttachmentRequest.model_validate(
            {**_attachment().model_dump(), "media_reference": "opaque"}
        )


def test_discord_attachment_metadata_comes_from_attachment_properties() -> None:
    message = SimpleNamespace(
        content="https://attacker.example/fake.png",
        attachments=(
            SimpleNamespace(
                id=10,
                url="https://cdn.discordapp.com/attachments/1/2/image.png",
                filename="image.png",
                content_type="image/png",
                size=100,
                width=10,
                height=20,
            ),
            SimpleNamespace(
                id=11,
                url="https://attacker.example/file.txt",
                filename="file.txt",
                content_type="text/plain",
                size=20,
                width=None,
                height=None,
            ),
        ),
    )
    attachments = AiModerationCog._media_attachments(message)
    assert len(attachments) == 1
    assert str(attachments[0].download_url).startswith("https://cdn.discordapp.com/")
    assert "attacker.example/fake.png" not in str(attachments[0].download_url)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("attachments", "expected_path"),
    (((), "/moderation/messages"), ((_attachment(),), "/moderation/media")),
)
async def test_api_client_routes_text_and_media_to_one_decision_endpoint(
    attachments: tuple[MediaAttachmentRequest, ...],
    expected_path: str,
) -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            request=request,
            json={
                "dataset_event_id": 1,
                "risk_score": 50,
                "severity": 4,
                "confidence": 0.9,
                "latency_ms": 10,
                "decision_action": "DELETE_WARN",
                "primary_label": "SCAM",
                "labels": ["SCAM"],
                "rule_matches": [],
                "execution_plan": ["DELETE", "WARN"],
                "execution_status": "PENDING",
            },
        )

    client = AiModeratorApiClient("http://127.0.0.1:8000", "key", 1)
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        decision = await client.moderate(_request(attachments=attachments))
    finally:
        await client.close()

    assert captured[0].url.path == expected_path
    body = json.loads(captured[0].content)
    if attachments:
        assert body["message"]["raw_text"].startswith("https://attacker.example")
        assert body["attachments"][0]["attachment_id"] == "10"
        assert body["attachments"][0]["download_url"].startswith("https://cdn.discordapp.com/")
    else:
        assert "attachments" not in body
    assert decision.action == "DELETE_WARN"
