import asyncio

import pytest

from infrastructure.config import BotConfig
from infrastructure.database.repositories.role_repository import RoleRepository
from infrastructure.database.repositories.voice_repository import VoiceRepository
from presentation.bot import DiscordBot


def test_discord_bot_registers_application_commands_globally(monkeypatch):
    monkeypatch.delenv("ACTIVITY_ROTATION_INTERVAL_SECONDS", raising=False)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    config = BotConfig(
        discord_token="test-token",
        discord_owner_id=1,
        database_url="postgresql://test:test@localhost:5432/test",
        presence_activities="",
        _env_file=None,
    )

    try:
        bot = DiscordBot(config)

        assert bot._test_guilds is None
        assert bot._command_sync_flags.sync_global_commands is False
        assert bot._command_sync_flags.sync_guild_commands is False
        assert config.activity_rotation_interval_seconds == 600
        assert len(bot._presence_items) == 9
    finally:
        loop.close()
        asyncio.set_event_loop(None)


@pytest.mark.asyncio
async def test_role_repository_keeps_roles_scoped_by_guild(postgres_test_db):
    manager = postgres_test_db
    repository = RoleRepository(manager)

    await repository.sync_from_discord(
        100,
        [
            {
                "id": 10,
                "name": "Alpha",
                "color": 111,
                "position": 1,
            }
        ],
    )
    await repository.sync_from_discord(
        200,
        [
            {
                "id": 20,
                "name": "Beta",
                "color": 222,
                "position": 1,
            }
        ],
    )

    await repository.set_auto_assign(10, True, 100)
    await repository.set_public(10, True, 100)
    await repository.set_public(20, False, 200)

    guild_100_roles = await repository.get_all_roles(100)
    guild_200_roles = await repository.get_all_roles(200)

    assert [role["role_id"] for role in guild_100_roles] == [10]
    assert [role["role_id"] for role in guild_200_roles] == [20]
    assert await repository.get_auto_assign_roles(100) == [10]
    assert await repository.get_auto_assign_roles(200) == []
    assert await repository.get_public_roles(200) == []


@pytest.mark.asyncio
async def test_role_repository_requires_guild_without_legacy_default(postgres_test_db):
    manager = postgres_test_db
    repository = RoleRepository(manager)

    with pytest.raises(ValueError, match="guild_id is required"):
        await repository.get_all_roles()


@pytest.mark.asyncio
async def test_voice_repository_tracks_members_per_channel(postgres_test_db):
    manager = postgres_test_db
    repository = VoiceRepository(manager)

    await repository.add_member(10, 100, 42)
    await repository.add_member(10, 100, 99)
    await repository.add_member(20, 200, 77)

    assert await repository.get_member_ids(10) == [42, 99]

    await repository.remove_member(10, 42)
    assert await repository.get_member_ids(10) == [99]
    assert await repository.get_member_ids(20) == [77]

    await repository.clear_members(10)
    assert await repository.get_member_ids(10) == []
