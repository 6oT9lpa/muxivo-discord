from typing import Any

from activity.server.dependencies import get_db
from activity.server.services.access_service import ActivityAccessService
from infrastructure.config import get_config
from infrastructure.logging import get_logger


logger = get_logger(__name__)


class IntegrationsService:
    def __init__(self) -> None:
        self._access_service = ActivityAccessService()

    async def get_integrations(self, guild_id: int, access_token: str) -> dict[str, Any]:
        logger.info("Loading Activity integrations guild_id=%s", guild_id)
        await self._access_service.ensure_module_access(access_token, str(guild_id), "integrations")
        sources = await get_db().fetch_all(
            """
            SELECT platform, COUNT(*) AS count, SUM(CASE WHEN active = 1 THEN 1 ELSE 0 END) AS active_count
            FROM streamers
            WHERE guild_id = ?
            GROUP BY platform
            """,
            (guild_id,),
        )
        config = get_config()
        return {
            "discord_bot": {"status": "configured", "detail": "Discord Bot API is used by the running bot."},
            "creator_platforms": {
                "status": "configured",
                "poll_interval_seconds": config.creator_alert_poll_interval_seconds,
                "sources": sources,
            },
            "muxivo_core": {"status": "configured", "endpoint": config.muxivo_core_api_url},
            "database": {"status": "configured", "detail": "PostgreSQL stores bot state and activity data."},
        }
