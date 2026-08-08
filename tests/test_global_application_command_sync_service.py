from types import SimpleNamespace

import pytest

from application.services.global_application_command_sync_service import GlobalApplicationCommandSyncService


@pytest.mark.asyncio
async def test_global_command_sync_updates_existing_commands_and_preserves_entry_point() -> None:
    command_bodies = [
        SimpleNamespace(name="set", type=1),
        SimpleNamespace(name="list", type=1),
        SimpleNamespace(name="ai-policy", type=1),
    ]
    bot = _Bot(
        command_bodies,
        [
            {"id": "1", "name": "set", "type": 1},
            {"id": "99", "name": "Open Muxivo", "type": 4},
        ],
    )

    commands = await GlobalApplicationCommandSyncService().sync_global_commands(bot)

    assert commands == command_bodies
    assert bot.edited_commands == [(1, command_bodies[0])]
    assert bot.created_commands == command_bodies[1:]


class _Bot:
    def __init__(self, command_bodies: list[SimpleNamespace], existing_commands: list[dict[str, str | int]]) -> None:
        self.application_id = 1
        self._commands = [SimpleNamespace(body=command) for command in command_bodies]
        self._connection = SimpleNamespace(http=_Http(existing_commands))
        self.edited_commands: list[tuple[int, SimpleNamespace]] = []
        self.created_commands: list[SimpleNamespace] = []

    def application_commands_iterator(self):
        return iter(self._commands)

    async def edit_global_command(self, command_id: int, command: SimpleNamespace) -> None:
        self.edited_commands.append((command_id, command))

    async def create_global_command(self, command: SimpleNamespace) -> None:
        self.created_commands.append(command)

    async def delete_global_command(self, _: int) -> None:
        return None


class _Http:
    def __init__(self, commands: list[dict[str, str | int]]) -> None:
        self._commands = commands

    async def get_global_commands(self, _: int, *, with_localizations: bool) -> list[dict[str, str | int]]:
        assert with_localizations is True
        return self._commands
