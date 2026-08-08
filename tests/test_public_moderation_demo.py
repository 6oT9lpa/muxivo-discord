from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import activity.server.routers.public_moderation_demo as demo_router
from activity.server.services.public_moderation_demo_service import PublicModerationDemoService


@pytest.mark.asyncio
async def test_public_moderation_demo_service_forwards_text_without_discord_execution():
    client = SimpleNamespace(
        moderate=AsyncMock(
            return_value=SimpleNamespace(
                risk_score=91.4,
                action="DELETE_WARN",
                primary_label="SCAM",
                labels=("SCAM",),
                execution_plan=("DELETE", "WARN"),
            )
        )
    )
    service = PublicModerationDemoService(client=client)

    result = await service.classify("Suspicious promotion")

    request = client.moderate.await_args.args[0]
    assert request.raw_text == "Suspicious promotion"
    assert result == {
        "risk_score": 91.4,
        "action": "DELETE_WARN",
        "primary_label": "SCAM",
        "labels": ["SCAM"],
        "execution_plan": ["DELETE", "WARN"],
    }


def test_public_moderation_demo_endpoint_runs_the_complete_request_response_flow(monkeypatch):
    service = SimpleNamespace(
        classify=AsyncMock(
            return_value={
                "risk_score": 8.0,
                "action": "IGNORE",
                "primary_label": "SAFE",
                "labels": [],
                "execution_plan": ["IGNORE"],
            }
        )
    )
    monkeypatch.setattr(demo_router, "service", service)
    app = FastAPI()
    app.include_router(demo_router.router)

    response = TestClient(app).post("/api/public/moderation-demo/classify", json={"message": "Hello, Muxivo Discord!"})

    assert response.status_code == 200
    assert response.json()["action"] == "IGNORE"
    service.classify.assert_awaited_once_with("Hello, Muxivo Discord!")
