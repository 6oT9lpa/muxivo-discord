import pytest

from activity.server.services.health_service import ActivityHealthService


@pytest.mark.asyncio
async def test_health_reports_current_bot_components_and_stream_poll_interval(monkeypatch):
    service = ActivityHealthService()

    async def ensure_access(*_):
        return {"id": "42", "username": "admin"}, {"is_admin": True}

    async def bot_latency():
        return 31

    async def database_latency():
        return 4

    async def ai_latency():
        return 28

    monkeypatch.setattr(service._access_service, "ensure_module_access", ensure_access)
    monkeypatch.setattr(service._discord, "measure_latency", bot_latency)
    monkeypatch.setattr(service, "_measure_database_latency", database_latency)
    monkeypatch.setattr(service._muxivo_core, "measure_latency", ai_latency)

    health = await service.get_health("100", "token")
    signals = {signal.name: signal for signal in health.signals}

    assert signals["Bot latency"].latency_ms == 31
    assert signals["PostgreSQL"].latency_ms == 4
    assert signals["Muxivo Core"].latency_ms == 28
    assert signals["Stream platform polling"].value.startswith("Every ")
