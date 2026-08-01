from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from application.dto.ai_moderation_decision import AiModerationDecision
from application.dto.ai_moderation_request import AiModerationRequest
from application.services.user_moderation_context_builder import UserModerationContextBuilder
from presentation.cogs.ai_moderation_cog import AiModerationCog
from tests.test_ai_moderation_cog import (
    _ChannelService,
    _ElevatedSettings,
    _Events,
    _Punishments,
    _Queue,
)


@pytest.mark.asyncio
async def test_failed_action_reports_terminal_failure() -> None:
    settings = _ElevatedSettings()
    queue = _Queue()
    punishments = _Punishments()
    guild = SimpleNamespace(
        id=1,
        get_member=lambda _user_id: None,
        get_channel=lambda _channel_id: None,
    )
    cog = AiModerationCog(
        SimpleNamespace(get_guild=lambda _guild_id: guild),
        settings,
        _ChannelService(),
        queue,
        UserModerationContextBuilder(punishments, _Events(settings)),
        punishments,
    )

    async def fail(*_args, **_kwargs):
        raise RuntimeError("discord unavailable")

    async def no_log(*_args, **_kwargs):
        return None

    cog._execute_action = fail
    cog._send_log = no_log
    request = AiModerationRequest(
        guild_id=1,
        channel_id=2,
        user_id=3,
        message_id=4,
        raw_text="unsafe",
        created_at=datetime.now(timezone.utc),
    )
    decision = AiModerationDecision(
        event_id=9,
        guild_id=1,
        user_id=3,
        message_id=4,
        risk_score=80,
        action="DELETE",
        primary_label="SCAM",
        labels=("SCAM",),
        execution_plan=("DELETE",),
        dry_run=False,
    )

    await cog.handle_decision(request, decision)

    assert queue.actions == [(9, "DELETE", "FAILED", False)]
    assert settings.events[0][-1] == "FAILED"
