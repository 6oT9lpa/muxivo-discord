"""Native Discord authority checks used by the Console control API.

The Console proves the identity that initiated a request.  This component proves
that the same Discord identity is currently allowed to administer the target
guild, using Discord's bot API as the source of truth.
"""

import logging
from typing import Protocol

from activity.server.schemas.discord import DiscordRole
from activity.server.services.discord_service import DiscordService

logger = logging.getLogger(__name__)

_DISCORD_ADMINISTRATOR_PERMISSION = 1 << 3


class DiscordGuildAuthorityReader(Protocol):
    """The small Discord API surface needed for native guild authorization."""

    async def fetch_guild_owner_id(self, guild_id: str) -> str | None: ...

    async def fetch_member_role_ids(self, guild_id: str, user_id: str) -> set[int]: ...

    async def list_roles(self, guild_id: str) -> list[DiscordRole]: ...


class DiscordGuildAuthority:
    """Checks whether a Discord subject has administrator authority in a guild."""

    def __init__(self, discord: DiscordGuildAuthorityReader | None = None) -> None:
        self._discord = discord or DiscordService()

    async def has_administrator_permission(self, guild_id: str, user_id: str) -> bool:
        """Return whether ``user_id`` can administer ``guild_id`` at Discord now.

        The @everyone role is implicit in Discord member payloads, so it is
        included explicitly.  Guild owners have all permissions independently
        of their assigned roles.
        """
        if not _is_discord_snowflake(guild_id) or not _is_discord_snowflake(user_id):
            logger.warning("Rejected malformed Discord guild authority identifiers")
            return False

        owner_id = await self._discord.fetch_guild_owner_id(guild_id)
        if owner_id == user_id:
            return True

        member_role_ids = await self._discord.fetch_member_role_ids(guild_id, user_id)
        if not member_role_ids:
            logger.info(
                "Discord native authority denied because subject is not a guild member guild_id=%s",
                guild_id,
            )
            return False

        applicable_role_ids = member_role_ids | {int(guild_id)}
        permissions = 0
        for role in await self._discord.list_roles(guild_id):
            if int(role.id) in applicable_role_ids:
                permissions |= role.permissions

        return bool(permissions & _DISCORD_ADMINISTRATOR_PERMISSION)


def _is_discord_snowflake(value: str) -> bool:
    return value.isdecimal() and 1 <= len(value) <= 20
