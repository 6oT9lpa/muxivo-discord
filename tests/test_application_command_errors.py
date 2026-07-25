import pytest
from disnake.ext import commands

from presentation.bot import DiscordBot


class _Response:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    def is_done(self) -> bool:
        return False

    async def send_message(self, **kwargs) -> None:
        self.sent.append(kwargs)


class _Interaction:
    command = "labeling"

    def __init__(self) -> None:
        self.response = _Response()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "expected_title"),
    [
        (commands.NoPrivateMessage(), "Команда доступна только в личных сообщениях"),
        (commands.CheckFailure(), "Недостаточно прав"),
    ],
)
async def test_application_command_errors_are_actionable(error: Exception, expected_title: str) -> None:
    interaction = _Interaction()

    await DiscordBot.on_application_command_error(None, interaction, error)

    assert interaction.response.sent[0]["embed"].title == expected_title
    assert interaction.response.sent[0]["ephemeral"] is True
