import pytest

from presentation.cogs.labeling_cog import LabelingCog


class _Response:
    def __init__(self, done: bool) -> None:
        self._done = done
        self.messages: list[dict] = []

    def is_done(self) -> bool:
        return self._done

    async def send_message(self, **kwargs) -> None:
        self.messages.append(kwargs)


class _Followup:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def send(self, **kwargs) -> None:
        self.messages.append(kwargs)


class _Context:
    def __init__(self, done: bool) -> None:
        self.response = _Response(done)
        self.followup = _Followup()


class _DirectMessageContext(_Context):
    def __init__(self, actor_id: int) -> None:
        super().__init__(done=False)
        self.guild = None
        self.author = type("Author", (), {"id": actor_id})()


class _Bot:
    guilds: list = []


@pytest.mark.asyncio
async def test_labeling_denial_uses_initial_interaction_response() -> None:
    ctx = _Context(done=False)

    await LabelingCog._respond(ctx, "Denied", "No access", error=True)

    assert len(ctx.response.messages) == 1
    assert not ctx.followup.messages


@pytest.mark.asyncio
async def test_labeling_denial_uses_followup_after_interaction_acknowledged() -> None:
    ctx = _Context(done=True)

    await LabelingCog._respond(ctx, "Denied", "No access", error=True)

    assert not ctx.response.messages
    assert len(ctx.followup.messages) == 1


@pytest.mark.asyncio
async def test_labeling_parent_does_not_acknowledge_subcommand_interaction() -> None:
    ctx = _DirectMessageContext(actor_id=1)
    cog = LabelingCog(_Bot(), service=object(), owner_id=1)

    await LabelingCog.labeling.callback(cog, ctx)

    assert not ctx.response.messages
    assert not ctx.followup.messages


@pytest.mark.asyncio
async def test_labeling_manage_sends_server_selection_response() -> None:
    ctx = _DirectMessageContext(actor_id=1)
    cog = LabelingCog(_Bot(), service=object(), owner_id=1)

    await LabelingCog.manage.callback(cog, ctx)

    assert len(ctx.response.messages) == 1
    assert ctx.response.messages[0]["ephemeral"] is True
    assert "view" in ctx.response.messages[0]
