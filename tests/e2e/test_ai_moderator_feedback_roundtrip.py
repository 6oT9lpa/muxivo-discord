from __future__ import annotations

import asyncio
import os
import socket
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import httpx
import psycopg
import pytest

from application.dto.ai_moderation_request import AiModerationRequest
from infrastructure.ai.ai_moderator_api_client import AiModeratorApiClient


pytestmark = pytest.mark.skipif(
    not (os.getenv("E2E_AI_MODERATOR_ROOT") and os.getenv("TEST_POSTGRESQL_URL")),
    reason="E2E_AI_MODERATOR_ROOT and disposable TEST_POSTGRESQL_URL are required",
)


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.mark.asyncio
async def test_omnibot_client_moderation_and_feedback_roundtrip() -> None:
    ai_root = Path(os.environ["E2E_AI_MODERATOR_ROOT"]).resolve()
    port = _free_port()
    api_key = "e2e-internal-key-32-characters"
    environment = {
        **os.environ,
        "DATABASE_URL": os.environ["TEST_POSTGRESQL_URL"],
        "AI_MODERATOR_INTERNAL_API_KEY": api_key,
        "AI_MODERATOR_API_RUBERT_ENABLED": "false",
        "AI_MODERATOR_API_RUBERT_REQUIRED": "false",
        "AI_MODERATOR_MEDIA_ENABLED": "false",
        "AI_MODERATOR_API_HOST": "127.0.0.1",
        "AI_MODERATOR_API_PORT": str(port),
    }
    service_log = tempfile.TemporaryFile(mode="w+", encoding="utf-8")
    service_python = os.getenv("E2E_AI_MODERATOR_PYTHON", sys.executable)
    process = subprocess.Popen(
        [service_python, "main_api.py"],
        cwd=ai_root,
        env=environment,
        stdout=service_log,
        stderr=subprocess.STDOUT,
    )
    client = AiModeratorApiClient(f"http://127.0.0.1:{port}", api_key, 10)
    try:
        async with httpx.AsyncClient() as health_client:
            for _ in range(100):
                try:
                    response = await health_client.get(f"http://127.0.0.1:{port}/health")
                    if response.status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                if process.poll() is not None:
                    service_log.seek(0)
                    pytest.fail(f"AI Moderator exited during startup:\n{service_log.read()[-4_000:]}")
                await asyncio.sleep(0.1)
            else:
                service_log.seek(0)
                pytest.fail(
                    f"AI Moderator did not become ready; health={response.json()}:\n"
                    f"{service_log.read()[-4_000:]}"
                )
            if response.json()["status"] != "ok":
                service_log.seek(0)
                pytest.fail(
                    f"AI Moderator readiness is degraded; health={response.json()}:\n"
                    f"{service_log.read()[-12_000:]}"
                )

        request = AiModerationRequest(
            guild_id=9001,
            channel_id=9002,
            user_id=9003,
            message_id=9004,
            raw_text="ordinary integration test message",
            created_at=datetime.now(timezone.utc),
        )
        decision = await client.moderate(request)
        idempotency_key = "e2e-feedback-9001-9004"
        first = await client.submit_feedback(
            guild_id=request.guild_id,
            message_id=request.message_id,
            feedback_type="confirmed",
            labels=decision.labels,
            primary_label=decision.primary_label,
            severity=decision.severity,
            recommended_action=decision.action,
            original_action=decision.action,
            moderator_id="a" * 64,
            idempotency_key=idempotency_key,
        )
        duplicate = await client.submit_feedback(
            guild_id=request.guild_id,
            message_id=request.message_id,
            feedback_type="confirmed",
            labels=decision.labels,
            primary_label=decision.primary_label,
            severity=decision.severity,
            recommended_action=decision.action,
            original_action=decision.action,
            moderator_id="a" * 64,
            idempotency_key=idempotency_key,
        )

        assert first["status"] == "accepted"
        assert duplicate["status"] == "duplicate"
        with psycopg.connect(os.environ["TEST_POSTGRESQL_URL"]) as database:
            row = database.execute(
                """
                SELECT event.correlation_id, feedback.correlation_id, feedback.idempotency_key
                FROM ai_message_events AS event
                JOIN ai_feedback_labels AS feedback ON feedback.event_id = event.id
                WHERE event.guild_id = %s AND event.message_id = %s
                """,
                (str(request.guild_id), str(request.message_id)),
            ).fetchone()
        assert row is not None
        assert all(row)
        assert row[2] == idempotency_key
    finally:
        await client.close()
        if os.name == "nt":
            import psutil

            try:
                parent = psutil.Process(process.pid)
                children = parent.children(recursive=True)
                for child in children:
                    child.terminate()
                parent.terminate()
                _, alive = psutil.wait_procs([parent, *children], timeout=10)
                for remaining in alive:
                    remaining.kill()
            except psutil.NoSuchProcess:
                pass
        else:
            process.terminate()
        if process.poll() is None:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        service_log.close()
