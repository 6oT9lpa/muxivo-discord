from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from application.dto.ai_moderation_decision import AiModerationDecision
from application.dto.ai_moderation_request import AiModerationRequest
from infrastructure.ai.ai_moderator_api_client import AiModeratorApiClient
from infrastructure.logging import get_logger

logger = get_logger(__name__)


class AiModerationQueue:
    def __init__(self, client: AiModeratorApiClient, worker_count: int, max_size: int, on_decision: Callable[[AiModerationRequest, AiModerationDecision], Awaitable[None]]) -> None:
        self._client = client
        self._worker_count = worker_count
        self._queue: asyncio.Queue[AiModerationRequest] = asyncio.Queue(maxsize=max_size)
        self._on_decision = on_decision
        self._workers: list[asyncio.Task[None]] = []

    async def start(self) -> None:
        if self._workers:
            return
        self._workers = [asyncio.create_task(self._worker(index), name=f"ai-moderation-{index}") for index in range(self._worker_count)]
        logger.info("AI moderation queue started workers=%s", self._worker_count)

    async def stop(self) -> None:
        for worker in self._workers:
            worker.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        close = getattr(self._client, "close", None)
        if close is not None:
            await close()
        logger.info("AI moderation queue stopped")

    def submit(self, request: AiModerationRequest) -> bool:
        if self._queue.full():
            logger.warning("AI moderation queue full guild_id=%s message_id=%s", request.guild_id, request.message_id)
            return False
        self._queue.put_nowait(request)
        return True

    async def report_action(self, event_id: int, action: str, status: str, dry_run: bool) -> None:
        await self._client.report_action(event_id, action, status, dry_run)

    async def _worker(self, worker_id: int) -> None:
        while True:
            request = await self._queue.get()
            try:
                decision = await self._client.moderate(request)
                await self._on_decision(request, decision)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("AI moderation request failed worker=%s message_id=%s error=%s", worker_id, request.message_id, type(exc).__name__)
            finally:
                self._queue.task_done()
