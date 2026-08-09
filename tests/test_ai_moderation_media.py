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


def test_discord_attachment_uses_filename_when_discord_omits_content_type() -> None:
    message = SimpleNamespace(
        attachments=(
            SimpleNamespace(
                id=12,
                url="https://cdn.discordapp.com/attachments/1/2/animated.gif",
                filename="animated.gif",
                content_type=None,
                size=100,
                width=10,
                height=20,
            ),
        ),
    )

    attachments = AiModerationCog._media_attachments(message)
    assert len(attachments) == 1
    assert attachments[0].content_type == "image/gif"
    assert attachments[0].file_size == 100


def test_discord_cdn_gif_link_is_sent_to_media_moderation() -> None:
    message = SimpleNamespace(
        attachments=(),
        content="<https://cdn.discordapp.com/attachments/1/2/c8f07691d819d510.gif>",
    )

    attachments = AiModerationCog._media_attachments(message)

    assert len(attachments) == 1
    assert attachments[0].content_type == "image/gif"
    assert attachments[0].file_size is None
    assert str(attachments[0].download_url).endswith("c8f07691d819d510.gif")


def test_gif_cdn_url_is_removed_from_text_moderation_but_caption_and_other_link_remain() -> None:
    """A GIF's delivery link is media input, not text that should trigger URL rules."""
    gif_url = "https://cdn.discordapp.com/attachments/1/2/picker.gif?ex=abc&is=def&hm=0123"
    message = SimpleNamespace(
        attachments=(),
        content=f"see GIF: <{gif_url}> and docs https://example.com/rules",
        embeds=(),
    )

    attachments = AiModerationCog._media_attachments(message)
    text = AiModerationCog._media_text(message, attachments)

    assert len(attachments) == 1
    assert gif_url not in text
    assert text == "see GIF:  and docs https://example.com/rules"


def test_gif_preview_url_with_stale_signature_is_removed_using_discord_attachment_path() -> None:
    """The stale content preview must be removed when OCR uses a live thumbnail URL."""
    path = "/attachments/1/2/picker.gif"
    thumbnail_url = f"https://cdn.discordapp.com{path}?ex=live&is=live&hm=valid"
    content_url = f"https://media.discordapp.net{path}?width=480&height=270&expired=1"
    message = SimpleNamespace(
        attachments=(),
        content=f"{content_url} caption",
        embeds=(SimpleNamespace(video=None, image=None, thumbnail=SimpleNamespace(url=thumbnail_url), url=thumbnail_url),),
    )

    attachments = AiModerationCog._media_attachments(message)
    text = AiModerationCog._media_text(message, attachments)

    assert len(attachments) == 1
    assert text == "caption"


def test_non_discord_image_url_is_not_downloaded_by_bot() -> None:
    message = SimpleNamespace(attachments=(), content="https://attacker.example/payload.gif")
    assert AiModerationCog._media_attachments(message) == ()


def test_discord_cdn_gif_markdown_link_keeps_signed_url_intact() -> None:
    url = "https://cdn.discordapp.com/attachments/1/2/image.gif?ex=abc&is=def&hm=0123"
    message = SimpleNamespace(attachments=(), content=f"[{url}]({url})")

    attachments = AiModerationCog._media_attachments(message)

    assert len(attachments) == 1
    assert str(attachments[0].download_url) == url


def test_discord_cdn_gif_link_decodes_html_escaped_query_delimiters() -> None:
    canonical_url = "https://cdn.discordapp.com/attachments/1/2/image.gif?ex=abc&is=def&hm=0123"
    message = SimpleNamespace(
        attachments=(),
        content=canonical_url.replace("&", "&amp;"),
    )

    attachments = AiModerationCog._media_attachments(message)

    assert len(attachments) == 1
    assert str(attachments[0].download_url) == canonical_url


def test_discord_gif_picker_embed_is_sent_to_media_moderation() -> None:
    message = SimpleNamespace(
        attachments=(),
        content="",
        embeds=(
            SimpleNamespace(
                # The GIF picker creates a gifv embed; Discord exposes the
                # actual bytes under video/image/thumbnail, not embed.url.
                video=SimpleNamespace(
                    url="https://media.tenor.com/abc123AAAAC/tenor.gif",
                    width=320,
                    height=180,
                ),
                image=None,
                thumbnail=None,
                url="https://tenor.com/view/example-gif-123",
            ),
        ),
    )

    attachments = AiModerationCog._media_attachments(message)

    assert len(attachments) == 1
    assert attachments[0].attachment_id.startswith("embed-0-")
    assert attachments[0].content_type == "image/gif"
    assert str(attachments[0].download_url) == "https://media.tenor.com/abc123AAAAC/tenor.gif"
    assert attachments[0].width == 320
    assert attachments[0].height == 180


def test_discord_gif_picker_discord_cdn_thumbnail_is_sent_to_media_moderation() -> None:
    """Discord's picker may produce an image embed with only thumbnail.url."""
    url = "https://cdn.discordapp.com/attachments/1/2/picker.gif?ex=abc&is=def&hm=0123"
    message = SimpleNamespace(
        attachments=(),
        content="",
        embeds=(
            SimpleNamespace(
                type="image",
                video=None,
                image=None,
                thumbnail=SimpleNamespace(url=url.replace("&", "&amp;"), width=3368, height=1658),
                url=url.replace("&", "&amp;"),
            ),
        ),
    )

    attachments = AiModerationCog._media_attachments(message)

    assert len(attachments) == 1
    assert attachments[0].attachment_id.startswith("embed-0-")
    assert attachments[0].content_type == "image/gif"
    assert str(attachments[0].download_url) == url
    assert attachments[0].width == 3368
    assert attachments[0].height == 1658


def test_discord_picker_embed_wins_over_the_same_cdn_file_in_message_content() -> None:
    """The text preview can have a stale signature while thumbnail.url is live."""
    path = "/attachments/1/2/picker.gif"
    embed_url = f"https://cdn.discordapp.com{path}?ex=live&is=live&hm=valid"
    content_url = f"https://media.discordapp.net{path}?width=480&height=270&expired=1"
    message = SimpleNamespace(
        attachments=(),
        content=content_url,
        embeds=(SimpleNamespace(video=None, image=None, thumbnail=SimpleNamespace(url=embed_url), url=embed_url),),
    )

    attachments = AiModerationCog._media_attachments(message)

    assert len(attachments) == 1
    assert attachments[0].attachment_id.startswith("embed-")
    assert str(attachments[0].download_url) == embed_url


def test_discord_gif_picker_embed_decodes_html_escaped_query_delimiters() -> None:
    canonical_url = "https://media.tenor.com/abc123AAAAC/tenor.gif?x=1&y=2"
    message = SimpleNamespace(
        attachments=(),
        content="",
        embeds=(
            SimpleNamespace(
                video=SimpleNamespace(url=canonical_url.replace("&", "&amp;"), width=320, height=180),
                image=None,
                thumbnail=None,
            ),
        ),
    )

    attachments = AiModerationCog._media_attachments(message)

    assert len(attachments) == 1
    assert str(attachments[0].download_url) == canonical_url


def test_discord_gif_picker_ignores_untrusted_embed_media_url() -> None:
    message = SimpleNamespace(
        attachments=(),
        content="",
        embeds=(
            SimpleNamespace(
                video=SimpleNamespace(url="https://attacker.example/payload.gif", width=1, height=1),
                image=None,
                thumbnail=None,
            ),
        ),
    )

    assert AiModerationCog._media_attachments(message) == ()


@pytest.mark.parametrize(
    ("content", "attachments", "expected"),
    (
        ("", (), True),
        ("https://tenor.com/view/example", (), True),
        ("https://giphy.com/gifs/example", (), True),
        ("hello", (), False),
        ("", (SimpleNamespace(id=1),), False),
    ),
)
def test_gif_embed_hydration_delay_is_limited_to_possible_picker_messages(content, attachments, expected) -> None:
    message = SimpleNamespace(content=content, attachments=attachments)
    assert AiModerationCog._should_wait_for_gif_embed(message) is expected


def test_late_embed_hydration_is_detected_without_treating_it_as_user_edit() -> None:
    url = "https://cdn.discordapp.com/attachments/1/2/picker.gif"
    before = SimpleNamespace(attachments=(), content="", embeds=(), stickers=())
    after = SimpleNamespace(
        attachments=(),
        content="",
        stickers=(),
        embeds=(SimpleNamespace(video=None, image=None, thumbnail=SimpleNamespace(url=url), url=url),),
    )

    assert AiModerationCog._is_late_embed_hydration(before, after) is True


def test_user_attachment_edit_is_not_mistaken_for_late_embed_hydration() -> None:
    before = SimpleNamespace(attachments=(), content="", embeds=(), stickers=())
    after = SimpleNamespace(
        content="",
        embeds=(),
        stickers=(),
        attachments=(
            SimpleNamespace(
                id=3,
                url="https://cdn.discordapp.com/attachments/1/2/picker.gif",
                filename="picker.gif",
                content_type="image/gif",
                size=10,
                width=None,
                height=None,
            ),
        ),
    )

    assert AiModerationCog._is_late_embed_hydration(before, after) is False


@pytest.mark.asyncio
async def test_gif_hydration_retries_until_discord_exposes_cdn_thumbnail(monkeypatch) -> None:
    """Do not submit the empty CREATE before Discord finishes its rich embed."""
    url = "https://cdn.discordapp.com/attachments/1/2/picker.gif"
    hydrated = SimpleNamespace(
        id=7,
        guild=SimpleNamespace(id=1),
        attachments=(),
        content="",
        embeds=(SimpleNamespace(video=None, image=None, thumbnail=SimpleNamespace(url=url, width=1, height=1), url=url),),
    )

    class Channel:
        calls = 0

        async def fetch_message(self, message_id):
            assert message_id == 7
            self.calls += 1
            return initial if self.calls == 1 else hydrated

    channel = Channel()
    initial = SimpleNamespace(id=7, guild=SimpleNamespace(id=1), attachments=(), content="", embeds=(), channel=channel)
    cog = object.__new__(AiModerationCog)
    cog._pending_media_hydration = {7: initial}
    cog._media_hydration_tasks = {}
    cog._submitted_hydrated_media_ids = __import__("collections").OrderedDict()
    submitted = []
    cog._queue = SimpleNamespace(submit=lambda request: submitted.append(request) or True)
    built = []

    async def build_request(message, event_type):
        built.append((message, event_type))
        return object()

    monkeypatch.setattr(cog, "_build_request", build_request)
    monkeypatch.setattr(AiModerationCog, "_GIF_EMBED_HYDRATION_POLL_SECONDS", 0)
    monkeypatch.setattr(AiModerationCog, "_GIF_EMBED_HYDRATION_ATTEMPTS", 3)

    await cog._submit_after_media_hydration(7)

    assert channel.calls == 2
    assert built == [(hydrated, "CREATE")]
    assert len(submitted) == 1
    assert cog._pending_media_hydration == {}
    assert tuple(cog._submitted_hydrated_media_ids) == (7,)


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
                "attachments": ([{"attachment_id": "10", "status": "analyzed"}] if attachments else []),
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
    assert decision.media_analysis_succeeded is bool(attachments)


def test_api_client_redacts_validation_error_values() -> None:
    response = httpx.Response(
        422,
        json={
            "detail": [
                {
                    "loc": ["body", "attachments", 0, "file_size"],
                    "type": "less_than_equal",
                    "input": 15_000_000,
                }
            ]
        },
    )

    assert AiModeratorApiClient._safe_error_summary(response) == (
        ("attachments.0.file_size", "less_than_equal"),
    )


def test_api_client_keeps_core_safe_error_code_without_response_text() -> None:
    response = httpx.Response(
        500,
        json={"code": "internal_error", "message": "Internal service error", "correlation_id": "secret"},
    )

    assert AiModeratorApiClient._safe_error_summary(response) == (("code", "internal_error"),)
