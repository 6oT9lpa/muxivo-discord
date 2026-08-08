import asyncio

import httpx
import pytest
from fastapi import HTTPException

from activity.server.schemas.media_policy import MediaPolicyPayload
from activity.server.services.ai_moderation_service import AiModerationService


class _AccessStub:
    async def ensure_module_access(self, *_args: object) -> None:
        return None

    async def fetch_user_context(self, *_args: object) -> dict[str, object]:
        return {"user": {"id": "456"}}


class _ClientStub:
    def __init__(self, *, conflict: bool = False, unavailable: bool = False) -> None:
        self.conflict = conflict
        self.unavailable = unavailable
        self.saved = False
        self.reset = False
        self.closed = False

    async def get_media_policy(self, _guild_id: int) -> dict[str, object]:
        if self.unavailable:
            request = httpx.Request("GET", "http://muxivo-core/policies/media")
            raise httpx.ConnectError("offline", request=request)
        if self.reset:
            return {"source": "YAML_DEFAULT", "revision": 0, "media": {}}
        return {"source": "DATABASE", "revision": 4, "media": {}}

    async def save_media_policy(self, **_kwargs: object) -> dict[str, object]:
        if self.conflict:
            request = httpx.Request("PUT", "http://muxivo-core/policies/media")
            response = httpx.Response(409, request=request)
            raise httpx.HTTPStatusError("conflict", request=request, response=response)
        self.saved = True
        return {"source": "DATABASE", "revision": 4}

    async def reset_media_policy(self, **_kwargs: object) -> dict[str, object]:
        self.reset = True
        return {"source": "YAML_DEFAULT", "revision": 0}

    async def close(self) -> None:
        self.closed = True


def _service(client: _ClientStub) -> AiModerationService:
    service = AiModerationService()
    service._access_service = _AccessStub()
    service._media_policy_client = lambda: client  # type: ignore[method-assign]
    return service


def test_media_policy_save_and_reset_are_verified_by_reload() -> None:
    save_client = _ClientStub()
    payload = MediaPolicyPayload(
        guild_id=123,
        expected_revision=3,
        media={"ocr": {"enabled": True}},
    )
    saved = asyncio.run(_service(save_client).save_media_policy(payload, "token"))
    assert save_client.saved is True
    assert save_client.closed is True
    assert saved["source"] == "DATABASE"

    reset_client = _ClientStub()
    reset = asyncio.run(_service(reset_client).reset_media_policy(123, 4, "token"))
    assert reset_client.reset is True
    assert reset_client.closed is True
    assert reset["source"] == "YAML_DEFAULT"


def test_media_policy_revision_conflict_is_preserved() -> None:
    payload = MediaPolicyPayload(guild_id=123, expected_revision=3, media={})
    with pytest.raises(HTTPException) as raised:
        asyncio.run(_service(_ClientStub(conflict=True)).save_media_policy(payload, "token"))
    assert raised.value.status_code == 409


def test_media_policy_unavailable_is_reported_as_service_unavailable() -> None:
    with pytest.raises(HTTPException) as raised:
        asyncio.run(_service(_ClientStub(unavailable=True)).get_media_policy(123, "token"))
    assert raised.value.status_code == 503
