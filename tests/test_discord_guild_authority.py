import pytest

from activity.server.schemas.discord import DiscordRole
from activity.server.services.discord_guild_authority import DiscordGuildAuthority


class FakeDiscordGuildAuthorityReader:
    def __init__(
        self,
        *,
        owner_id: str | None,
        member_role_ids: set[int] | None,
        roles: list[DiscordRole]
    ) -> None:
        self.owner_id = owner_id
        self.member_role_ids = member_role_ids
        self.roles = roles

    async def fetch_guild_owner_id(self, guild_id: str) -> str | None:
        return self.owner_id

    async def fetch_member_role_ids_if_member(
        self, guild_id: str, user_id: str
    ) -> set[int] | None:
        return self.member_role_ids

    async def list_roles(self, guild_id: str) -> list[DiscordRole]:
        return self.roles


def role(role_id: str, permissions: int) -> DiscordRole:
    return DiscordRole(
        id=role_id,
        name="role",
        color=0,
        position=0,
        permissions=permissions,
        managed=False,
        mentionable=False,
    )


@pytest.mark.asyncio
async def test_guild_owner_is_authorized_without_an_administrator_role() -> None:
    service = DiscordGuildAuthority(
        FakeDiscordGuildAuthorityReader(owner_id="2", member_role_ids=set(), roles=[])
    )

    assert await service.has_administrator_permission("1", "2") is True


@pytest.mark.asyncio
async def test_member_with_administrator_role_is_authorized() -> None:
    service = DiscordGuildAuthority(
        FakeDiscordGuildAuthorityReader(
            owner_id="3",
            member_role_ids={22},
            roles=[role("1", 0), role("22", 8)],
        )
    )

    assert await service.has_administrator_permission("1", "2") is True


@pytest.mark.asyncio
async def test_everyone_administrator_permission_is_authorized() -> None:
    service = DiscordGuildAuthority(
        FakeDiscordGuildAuthorityReader(
            owner_id="3",
            member_role_ids=set(),
            roles=[role("1", 8)],
        )
    )

    assert await service.has_administrator_permission("1", "2") is True


@pytest.mark.asyncio
async def test_non_member_or_non_administrator_is_denied() -> None:
    service = DiscordGuildAuthority(
        FakeDiscordGuildAuthorityReader(
            owner_id="3", member_role_ids=None, roles=[role("1", 8)]
        )
    )

    assert await service.has_administrator_permission("1", "2") is False


@pytest.mark.asyncio
async def test_malformed_identifiers_are_denied_without_discord_calls() -> None:
    service = DiscordGuildAuthority(
        FakeDiscordGuildAuthorityReader(
            owner_id="3", member_role_ids={22}, roles=[role("1", 8)]
        )
    )

    assert await service.has_administrator_permission("not-a-guild", "2") is False
