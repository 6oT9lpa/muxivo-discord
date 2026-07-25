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
