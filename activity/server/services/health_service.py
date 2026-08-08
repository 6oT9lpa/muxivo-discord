import time
from typing import Optional

from activity.server.dependencies import get_db
from activity.server.schemas.activity import ActivityHealthResponse, ActivityHealthSignal
from activity.server.services.access_service import ActivityAccessService
from activity.server.services.discord_service import DiscordService
from activity.server.services.muxivo_core_health_probe import AiModeratorHealthProbe
from infrastructure.config import get_config
from infrastructure.logging import get_logger


logger = get_logger(__name__)


class ActivityHealthService:
    def __init__(self) -> None:
        self._access_service = ActivityAccessService()
        self._discord = DiscordService()
        config = get_config()
        self._muxivo_core = AiModeratorHealthProbe(
            config.muxivo_core_api_url,
            config.muxivo_core_request_timeout_seconds,
        )

    async def get_health(self, guild_id: str, access_token: str) -> ActivityHealthResponse:
        logger.info("Loading Activity health guild_id=%s", guild_id)
        await self._access_service.ensure_module_access(access_token, guild_id, "health")

        discord_latency = await self._discord.measure_latency()
        database_latency = await self._measure_database_latency()
        ai_latency = await self._muxivo_core.measure_latency()
        poll_interval_seconds = get_config().creator_alert_poll_interval_seconds

        return ActivityHealthResponse(
            guild_id=guild_id,
            bot_latency_ms=discord_latency,
            signals=[
                ActivityHealthSignal(
                    name="Bot latency",
                    value=f"{discord_latency} ms" if discord_latency is not None else "Unavailable",
                    status="operational" if discord_latency is not None else "degraded",
                    latency_ms=discord_latency,
                ),
                ActivityHealthSignal(
                    name="PostgreSQL",
                    value=f"{database_latency} ms" if database_latency is not None else "Unavailable",
                    status="operational" if database_latency is not None else "degraded",
                    latency_ms=database_latency,
                ),
                ActivityHealthSignal(
                    name="Muxivo Core",
                    value=f"{ai_latency} ms" if ai_latency is not None else "Unavailable",
                    status="operational" if ai_latency is not None else "degraded",
                    latency_ms=ai_latency,
                ),
                ActivityHealthSignal(
                    name="Stream platform polling",
                    value=f"Every {poll_interval_seconds} seconds",
                    status="operational",
                    latency_ms=poll_interval_seconds,
                ),
            ],
        )

    async def _measure_database_latency(self) -> Optional[int]:
        started = time.perf_counter()
        try:
            await get_db().fetch_one("SELECT 1 AS ok")
        except Exception:
            logger.exception("Activity database latency probe failed")
            return None
        latency = round((time.perf_counter() - started) * 1000)
        logger.info("Activity database latency measured latency_ms=%s", latency)
        return latency
