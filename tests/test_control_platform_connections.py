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


def read_token(organization_id: str, **overrides: object) -> str:
    return make_token(
        organization_id,
        resource="console.control_modules",
        action="read",
        **overrides,
    )


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


def test_lists_browser_ready_modules_with_a_read_assertion(monkeypatch) -> None:
    organization_id = str(uuid4())
    client = create_client(monkeypatch, verified=True)

    response = client.get(
        f"/control/v1/organizations/{organization_id}/modules",
        headers={"Authorization": f"Bearer {read_token(organization_id)}"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "key": "discord.health",
                "display_name": "Platform health",
                "platform": "discord",
                "capability": "view",
                "status": "available",
            },
            {
                "key": "discord.dashboard-summary",
                "display_name": "Dashboard summary",
                "platform": "discord",
                "capability": "view",
                "status": "available",
            },
            {
                "key": "discord.server-stats",
                "display_name": "Server stats",
                "platform": "discord",
                "capability": "view",
                "status": "available",
            },
        ]
    }


def test_returns_health_only_with_a_read_assertion(monkeypatch) -> None:
    organization_id = str(uuid4())
    client = create_client(monkeypatch, verified=True)

    class Snapshot:
        def model_dump(self, *, mode: str) -> dict[str, object]:
            assert mode == "json"
            return {"guild_id": "0", "signals": []}

    class FakeHealthService:
        async def get_platform_health(self) -> Snapshot:
            return Snapshot()

    monkeypatch.setattr(control, "health_service", FakeHealthService())
    response = client.get(
        f"/control/v1/organizations/{organization_id}/health",
        headers={"Authorization": f"Bearer {read_token(organization_id)}"},
    )

    assert response.status_code == 200
    assert response.json() == {"guild_id": "0", "signals": []}


def test_returns_dashboard_summary_only_for_the_assertion_bound_guild(
    monkeypatch,
) -> None:
    organization_id = str(uuid4())
    guild_id = "123456789012345678"
    client = create_client(monkeypatch, verified=True)

    class FakeDashboardService:
        async def get_control_summary(
            self, requested_guild_id: int
        ) -> dict[str, int | None]:
            assert requested_guild_id == int(guild_id)
            return {
                "messages_today": 42,
                "ai_flagged_today": 3,
                "creator_sources": 2,
                "bot_latency_ms": 12,
            }

    monkeypatch.setattr(control, "dashboard_service", FakeDashboardService())
    response = client.get(
        f"/control/v1/organizations/{organization_id}/connections/{guild_id}/dashboard",
        headers={
            "Authorization": f"Bearer {read_token(organization_id, platform_resource_id=guild_id)}"
        },
    )

    assert response.status_code == 200
    assert response.json()["metrics"]["messages_today"] == 42


def test_rejects_dashboard_request_when_the_signed_guild_does_not_match(
    monkeypatch,
) -> None:
    organization_id = str(uuid4())
    client = create_client(monkeypatch, verified=True)

    response = client.get(
        f"/control/v1/organizations/{organization_id}/connections/123/dashboard",
        headers={
            "Authorization": f"Bearer {read_token(organization_id, platform_resource_id='456')}"
        },
    )

    assert response.status_code == 403


def test_returns_server_stats_only_for_the_assertion_bound_guild(monkeypatch) -> None:
    organization_id = str(uuid4())
    guild_id = "123456789012345678"
    client = create_client(monkeypatch, verified=True)

    class FakeStatsService:
        async def get_server_stats_snapshot(
            self, requested_guild_id: int, period: int
        ) -> dict[str, object]:
            assert requested_guild_id == int(guild_id)
            assert period == 14
            return {
                "summary": {"period_days": 14, "total_messages": 120},
                "channels": [],
                "hourly": [],
                "daily": [],
            }

    monkeypatch.setattr(control, "stats_service", FakeStatsService())
    response = client.get(
        f"/control/v1/organizations/{organization_id}/connections/{guild_id}/server-stats?period=14",
        headers={
            "Authorization": f"Bearer {read_token(organization_id, platform_resource_id=guild_id)}"
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "guild_id": guild_id,
        "stats": {
            "summary": {"period_days": 14, "total_messages": 120},
            "channels": [],
            "hourly": [],
            "daily": [],
        },
    }


def test_rejects_server_stats_when_the_signed_guild_does_not_match(monkeypatch) -> None:
    organization_id = str(uuid4())
    client = create_client(monkeypatch, verified=True)

    class FakeStatsService:
        calls = 0

        async def get_server_stats_snapshot(self, guild_id: int, period: int):
            self.calls += 1
            return {}

    fake_stats = FakeStatsService()
    monkeypatch.setattr(control, "stats_service", fake_stats)
    response = client.get(
        f"/control/v1/organizations/{organization_id}/connections/123/server-stats",
        headers={
            "Authorization": f"Bearer {read_token(organization_id, platform_resource_id='456')}"
        },
    )

    assert response.status_code == 403
    assert fake_stats.calls == 0


def test_validates_server_stats_period_before_querying_service(monkeypatch) -> None:
    organization_id = str(uuid4())
    guild_id = "123456789012345678"
    client = create_client(monkeypatch, verified=True)

    response = client.get(
        f"/control/v1/organizations/{organization_id}/connections/{guild_id}/server-stats?period=366",
        headers={
            "Authorization": f"Bearer {read_token(organization_id, platform_resource_id=guild_id)}"
        },
    )

    assert response.status_code == 422
