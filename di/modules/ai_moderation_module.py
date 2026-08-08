from typing import Optional

from disnake.ext import commands

from application.services.ai_moderation_queue import AiModerationQueue
from application.services.ai_moderation_settings_service import AiModerationSettingsService
from application.services.user_moderation_context_builder import UserModerationContextBuilder
from infrastructure.ai.muxivo_core_api_client import AiModeratorApiClient
from infrastructure.logging import get_logger
from presentation.cogs.ai_moderation_cog import AiModerationCog

logger = get_logger(__name__)


class AiModerationModule:
    def __init__(self, container) -> None:
        self._container = container
        self._cog: Optional[AiModerationCog] = None

    async def get_cog(self, bot: commands.Bot) -> Optional[AiModerationCog]:
        if self._cog is not None:
            return self._cog
        api_key = self._container.config.muxivo_core_internal_api_key
        if api_key is None:
            logger.warning("AI moderation cog is disabled because MUXIVO_CORE_INTERNAL_API_KEY is missing")
            return None
        settings_service = await self._container.get_ai_moderation_settings_service()
        channel_service = await self._container.get_channel_service()
        context_builder = UserModerationContextBuilder(
            await self._container.get_punishment_repository(),
            await self._container.get_ai_moderation_repository(),
        )
        client = AiModeratorApiClient(
            self._container.config.muxivo_core_api_url,
            api_key.get_secret_value(),
            self._container.config.muxivo_core_request_timeout_seconds,
        )
        queue = AiModerationQueue(client, self._container.config.muxivo_core_worker_count, self._container.config.muxivo_core_queue_size, self._handle_decision)
        self._cog = AiModerationCog(
            bot,
            settings_service,
            channel_service,
            queue,
            context_builder,
            await self._container.get_punishment_repository(),
            await self._container.get_ai_moderation_repository(),
        )
        return self._cog

    async def _handle_decision(self, request, decision) -> None:
        if self._cog is not None:
            await self._cog.handle_decision(request, decision)

    async def shutdown(self) -> None:
        if self._cog is not None:
            await self._cog.shutdown()
            self._cog = None
