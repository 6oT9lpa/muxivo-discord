import base64
import hashlib
import hmac
import json
import time
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from activity.server.routers import control

KEY = b"k" * 32


def make_token(organization_id: str, **overrides: object) -> str:
    now = int(time.time())
    claims = {
        "iss": "muxivo-console",
        "aud": "muxivo-discord-control",
        "sub": str(uuid4()),
        "organization_id": organization_id,
        "platform_subject": "123456789012345678",
        "correlation_id": str(uuid4()),
        "resource": "console.platform_connections",
        "action": "manage",
        "iat": now,
        "exp": now + 60,
        **overrides,
    }
    encode = (
        lambda value: base64.urlsafe_b64encode(
            json.dumps(value, separators=(",", ":")).encode()
        )
        .rstrip(b"=")
        .decode()
    )
    header, payload = encode({"alg": "HS256", "typ": "JWT"}), encode(claims)
    signature = hmac.new(KEY, f"{header}.{payload}".encode(), hashlib.sha256).digest()
    return f"{header}.{payload}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}"


def create_client(monkeypatch, verified: bool) -> TestClient:
    class FakeAuthority:
        async def has_administrator_permission(
            self, guild_id: str, user_id: str
        ) -> bool:
            return verified

    monkeypatch.setenv(
        "MUXIVO_DISCORD_CONTROL_SIGNING_KEY", base64.b64encode(KEY).decode()
    )
    monkeypatch.setattr(control, "authority", FakeAuthority())
    app = FastAPI()
    app.include_router(control.router)
    return TestClient(app)


def test_verifies_native_discord_authority_for_valid_console_assertion(
    monkeypatch,
) -> None:
    organization_id = str(uuid4())
    client = create_client(monkeypatch, verified=True)

    response = client.post(
        f"/control/v1/organizations/{organization_id}/connections/verify",
        headers={"Authorization": f"Bearer {make_token(organization_id)}"},
        json={"platform": "discord", "external_resource_id": "123456789012345678"},
    )

    assert response.status_code == 200
    assert response.json() == {"verified": True}


def test_returns_not_verified_when_discord_native_authority_is_absent(
    monkeypatch,
) -> None:
    organization_id = str(uuid4())
    client = create_client(monkeypatch, verified=False)

    response = client.post(
        f"/control/v1/organizations/{organization_id}/connections/verify",
        headers={"Authorization": f"Bearer {make_token(organization_id)}"},
        json={"platform": "discord", "external_resource_id": "123456789012345678"},
    )

    assert response.status_code == 200
    assert response.json() == {"verified": False}


def test_rejects_assertion_for_a_different_organization(monkeypatch) -> None:
    client = create_client(monkeypatch, verified=True)

    response = client.post(
        f"/control/v1/organizations/{uuid4()}/connections/verify",
        headers={"Authorization": f"Bearer {make_token(str(uuid4()))}"},
        json={"platform": "discord", "external_resource_id": "123456789012345678"},
    )

    assert response.status_code == 403


def test_rejects_missing_or_invalid_control_assertion(monkeypatch) -> None:
    organization_id = str(uuid4())
    client = create_client(monkeypatch, verified=True)

    missing = client.post(
        f"/control/v1/organizations/{organization_id}/connections/verify",
        json={"platform": "discord", "external_resource_id": "123456789012345678"},
    )
    malformed = client.post(
        f"/control/v1/organizations/{organization_id}/connections/verify",
        headers={"Authorization": "Bearer not-a-token"},
        json={"platform": "discord", "external_resource_id": "123456789012345678"},
    )

    assert missing.status_code == 401
    assert malformed.status_code == 401
