import time
from typing import Optional

import httpx

from infrastructure.logging import get_logger


logger = get_logger(__name__)


class AiModeratorHealthProbe:
    """Measures whether the configured local AI moderation service is reachable."""

    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        self._health_url = f"{base_url.rstrip('/')}/health"
        self._timeout_seconds = timeout_seconds

    async def measure_latency(self) -> Optional[int]:
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds, trust_env=False) as client:
                response = await client.get(self._health_url)
            if response.status_code >= 400:
                logger.warning("Muxivo Core health probe failed status=%s", response.status_code)
                return None
        except httpx.HTTPError:
            logger.exception("Muxivo Core health probe raised an HTTP error")
            return None
        latency = round((time.perf_counter() - started) * 1000)
        logger.info("Muxivo Core latency measured latency_ms=%s", latency)
        return latency
