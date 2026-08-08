from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import disnake
import pytest

from application.dto.ai_moderation_decision import AiModerationDecision
from application.dto.ai_moderation_request import AiModerationRequest
from application.services.user_moderation_context_builder import UserModerationContextBuilder
from core.domain.value_objects import PunishmentType
from presentation.cogs.ai_moderation_cog import AiModerationCog


class _Bot:
    def get_guild(self, guild_id): return _Guild(guild_id)
    def get_cog(self, _): return None


class _Guild:
    def __init__(self, guild_id): self.id = guild_id
    def get_member(self, _): return None
    def get_channel(self, _): return None


class _Settings:
    def __init__(self): self.events = []
    async def get_policy(self, _): return {}
    async def record_event(self, *event): self.events.append(event)


class _FailingEventSettings(_Settings):
    async def record_event(self, *_event):
        raise RuntimeError("database temporarily unavailable")


class _ElevatedSettings(_Settings):
    async def get_policy(self, _):
        return {"enforcement_mode": "ELEVATED", "beta_enforcement_acknowledged": True}


class _AutomatedTimeoutSettings(_Settings):
    async def get_policy(self, _):
        return {
            "enforcement_mode": "ELEVATED",
            "beta_enforcement_acknowledged": True,
            "allow_automated_timeout": True,
        }


class _Queue:
    def __init__(self): self.actions = []
    async def report_action(self, *action): self.actions.append(action)


class _ChannelService:
    async def get_purpose_channel(self, *_): return None


class _Punishments:
    def __init__(self):
        self.added = []

    async def list_for_user(self, *_args, **_kwargs): return []
    async def add_punishment(self, *args, **kwargs):
        self.added.append((args, kwargs))
        return 1


class _SentChannel:
    def __init__(self, channel_id=2):
        self.id = channel_id
        self.embeds = []

    async def send(self, *, embed):
        self.embeds.append(embed)


class _Events:
    def __init__(self, settings): self._settings = settings
    async def count_ai_deleted_messages(self, guild_id, user_id, _since):
        return sum(event[0] == guild_id and event[3] == user_id and event[5] == "DELETE" and event[-1] == "SUCCESS" for event in self._settings.events)


@pytest.mark.asyncio
async def test_shadow_mode_suppresses_delete_and_records_the_recommendation() -> None:
    settings = _Settings(); queue = _Queue(); punishments = _Punishments()
    builder = UserModerationContextBuilder(punishments, _Events(settings))
    cog = AiModerationCog(_Bot(), settings, _ChannelService(), queue, builder, punishments)
    executed = []

    async def execute(_guild, _member, _message, action, _dry_run, _decision, _request): executed.append(action)

    cog._execute_action = execute
    request = AiModerationRequest(guild_id=1, channel_id=2, user_id=3, message_id=4, raw_text="unsafe", created_at=datetime.now(timezone.utc))
    decision = AiModerationDecision(event_id=1, guild_id=1, user_id=3, message_id=4, risk_score=90, action="DELETE", primary_label="SCAM", labels=("SCAM",), execution_plan=("DELETE",), dry_run=False)

    await cog.handle_decision(request, decision)
    context = await builder.build(object(), 1, 3, 30)

    assert executed == ["REVIEW"]
    assert queue.actions == [(1, "REVIEW", "SUCCESS", False)]
    assert settings.events[0][5] == "REVIEW"
    assert settings.events[0][6] == "DELETE"
    assert context.punishments.ai_deleted_messages_in_window == 0


@pytest.mark.asyncio
async def test_decision_embed_is_attempted_when_event_persistence_fails() -> None:
    settings = _FailingEventSettings(); queue = _Queue(); punishments = _Punishments()
    cog = AiModerationCog(_Bot(), settings, _ChannelService(), queue, UserModerationContextBuilder(punishments, _Events(settings)), punishments)
    sent = []

    async def send_log(_guild, request, decision, status):
        sent.append((request.message_id, decision.action, status))

    cog._send_log = send_log
    request = AiModerationRequest(guild_id=1, channel_id=2, user_id=3, message_id=4, raw_text="unsafe", created_at=datetime.now(timezone.utc))
    decision = AiModerationDecision(event_id=1, guild_id=1, user_id=3, message_id=4, risk_score=90, action="REVIEW", primary_label="SCAM", labels=("SCAM",), execution_plan=("REVIEW",), dry_run=True)

    await cog.handle_decision(request, decision)

    assert sent == [(4, "REVIEW", "SUCCESS")]


@pytest.mark.asyncio
async def test_decision_embed_uses_resolved_fallback_destination() -> None:
    settings = _Settings(); queue = _Queue(); punishments = _Punishments()
    cog = AiModerationCog(_Bot(), settings, _ChannelService(), queue, UserModerationContextBuilder(punishments, _Events(settings)), punishments)
    channel = _SentChannel()

    async def fallback_destination(*_):
        return [("source_channel", channel)]

    cog._resolve_log_channels = fallback_destination
    request = AiModerationRequest(guild_id=1, channel_id=2, user_id=3, message_id=4, raw_text="unsafe", created_at=datetime.now(timezone.utc))
    decision = AiModerationDecision(event_id=1, guild_id=1, user_id=3, message_id=4, risk_score=90, action="REVIEW", primary_label="SCAM", labels=("SCAM",), execution_plan=("REVIEW",), dry_run=True)

    await cog._send_log(_Guild(1), request, decision, "SUCCESS")

    assert len(channel.embeds) == 1
    assert channel.embeds[0].title == "AI moderation decision"


@pytest.mark.asyncio
async def test_multi_step_action_reports_only_the_final_decision() -> None:
    settings = _ElevatedSettings(); queue = _Queue(); punishments = _Punishments()
    cog = AiModerationCog(_Bot(), settings, _ChannelService(), queue, UserModerationContextBuilder(punishments, _Events(settings)), punishments)
    executed = []

    async def execute(_guild, _member, _message, action, _dry_run, _decision, _request):
        executed.append(action)

    cog._execute_action = execute
    request = AiModerationRequest(guild_id=1, channel_id=2, user_id=3, message_id=4, raw_text="unsafe", created_at=datetime.now(timezone.utc))
    decision = AiModerationDecision(event_id=1, guild_id=1, user_id=3, message_id=4, risk_score=90, action="DELETE_WARN", primary_label="SCAM", labels=("SCAM",), execution_plan=("DELETE_WARN",), dry_run=False)

    await cog.handle_decision(request, decision)

    assert executed == ["DELETE", "WARN"]
    assert queue.actions == [(1, "DELETE_WARN", "SUCCESS", False)]


@pytest.mark.parametrize(
    ("owner_id", "bot_role_position", "member_role_position", "can_timeout"),
    (
        (3, 10, 1, True),
        (999, 10, 10, True),
        (999, 10, 1, False),
    ),
)
def test_unmanageable_member_action_falls_back_to_delete_warn(
    owner_id: int,
    bot_role_position: int,
    member_role_position: int,
    can_timeout: bool,
) -> None:
    cog = object.__new__(AiModerationCog)
    guild = SimpleNamespace(
        owner_id=owner_id,
        me=SimpleNamespace(
            id=99,
            top_role=SimpleNamespace(position=bot_role_position),
            guild_permissions=SimpleNamespace(moderate_members=can_timeout),
        ),
    )
    member = SimpleNamespace(
        id=3,
        top_role=SimpleNamespace(position=member_role_position),
        guild_permissions=SimpleNamespace(administrator=False),
        roles=(),
    )
    decision = AiModerationDecision(
        event_id=1,
        guild_id=1,
        user_id=3,
        message_id=4,
        risk_score=100,
        action="TIMEOUT",
        primary_label="THREAT",
        labels=("THREAT", "TOXIC"),
        execution_plan=("DELETE", "TIMEOUT"),
        dry_run=False,
    )

    adjusted = cog._limit_to_executable_member_action(guild, member, decision)

    assert adjusted.action == "DELETE_WARN"
    assert adjusted.proposed_action == "TIMEOUT"
    assert adjusted.execution_plan == ("DELETE", "WARN")


def test_test_mode_preserves_unmanageable_member_action() -> None:
    cog = object.__new__(AiModerationCog)
    guild = SimpleNamespace(owner_id=3)
    member = SimpleNamespace(id=3)
    decision = AiModerationDecision(
        event_id=1,
        guild_id=1,
        user_id=3,
        message_id=4,
        risk_score=100,
        action="TIMEOUT",
        primary_label="THREAT",
        labels=("THREAT",),
        execution_plan=("DELETE", "TIMEOUT"),
        dry_run=True,
    )

    assert cog._limit_to_executable_member_action(guild, member, decision) is decision


@pytest.mark.parametrize(
    ("action", "permission_name"),
    (
        ("TIMEOUT", "moderate_members"),
        ("KICK", "kick_members"),
        ("BAN", "ban_members"),
    ),
)
def test_manageable_high_impact_member_action_is_preserved(
    action: str,
    permission_name: str,
) -> None:
    cog = object.__new__(AiModerationCog)
    permissions = SimpleNamespace(
        moderate_members=False,
        kick_members=False,
        ban_members=False,
    )
    setattr(permissions, permission_name, True)
    guild = SimpleNamespace(
        owner_id=999,
        me=SimpleNamespace(
            id=99,
            top_role=SimpleNamespace(position=10),
            guild_permissions=permissions,
        ),
    )
    member = SimpleNamespace(
        id=3,
        top_role=SimpleNamespace(position=1),
        guild_permissions=SimpleNamespace(administrator=False),
        roles=(),
    )
    decision = AiModerationDecision(
        event_id=1,
        guild_id=1,
        user_id=3,
        message_id=4,
        risk_score=100,
        action=action,
        primary_label="THREAT",
        labels=("THREAT",),
        execution_plan=("DELETE", action),
        dry_run=False,
    )

    assert cog._limit_to_executable_member_action(guild, member, decision) is decision


@pytest.mark.asyncio
async def test_discord_forbidden_timeout_falls_back_to_warning_after_delete() -> None:
    settings = _AutomatedTimeoutSettings()
    queue = _Queue()
    punishments = _Punishments()
    member = SimpleNamespace(
        id=3,
        top_role=SimpleNamespace(position=1),
        guild_permissions=SimpleNamespace(administrator=False),
        roles=(),
    )
    guild = SimpleNamespace(
        id=1,
        owner_id=999,
        me=SimpleNamespace(
            id=99,
            top_role=SimpleNamespace(position=10),
            guild_permissions=SimpleNamespace(moderate_members=True),
        ),
        get_member=lambda _user_id: member,
        get_channel=lambda _channel_id: None,
    )
    bot = SimpleNamespace(get_guild=lambda _guild_id: guild)
    cog = AiModerationCog(
        bot,
        settings,
        _ChannelService(),
        queue,
        UserModerationContextBuilder(punishments, _Events(settings)),
        punishments,
    )
    executed = []
    sent_logs = []

    async def execute(_guild, _member, _message, action, _dry_run, _decision, _request):
        executed.append(action)
        if action == "TIMEOUT":
            response = SimpleNamespace(status=403, reason="Forbidden")
            raise disnake.Forbidden(response, {"message": "Missing Permissions", "code": 50013})

    async def send_log(_guild, _request, final_decision, status):
        sent_logs.append((final_decision.action, final_decision.proposed_action, status))

    cog._execute_action = execute
    cog._send_log = send_log
    request = AiModerationRequest(
        guild_id=1,
        channel_id=2,
        user_id=3,
        message_id=4,
        raw_text="unsafe",
        created_at=datetime.now(timezone.utc),
    )
    decision = AiModerationDecision(
        event_id=1,
        guild_id=1,
        user_id=3,
        message_id=4,
        risk_score=100,
        action="TIMEOUT",
        primary_label="THREAT",
        labels=("THREAT", "TOXIC"),
        execution_plan=("TIMEOUT",),
        dry_run=False,
    )

    await cog.handle_decision(request, decision)

    assert executed == ["DELETE", "TIMEOUT", "WARN"]
    assert queue.actions == [(1, "DELETE_WARN", "SUCCESS", False)]
    assert settings.events[0][5:7] == ("DELETE_WARN", "TIMEOUT")
    assert settings.events[0][-1] == "SUCCESS"
    assert sent_logs == [("DELETE_WARN", "TIMEOUT", "SUCCESS")]
    assert punishments.added[0][0][2] == PunishmentType.WARN


@pytest.mark.parametrize(("severity", "risk_score", "expected"), [(1, 20, timedelta(minutes=10)), (2, 20, timedelta(minutes=20)), (3, 20, timedelta(hours=1)), (4, 20, timedelta(hours=6)), (5, 20, timedelta(hours=24)), (1, 90, timedelta(hours=24))])
def test_timeout_duration_uses_severity_and_risk(severity: int, risk_score: float, expected: timedelta) -> None:
    decision = AiModerationDecision(event_id=1, guild_id=1, user_id=3, message_id=4, risk_score=risk_score, severity=severity, action="TIMEOUT", primary_label="THREAT", labels=("THREAT",), execution_plan=("TIMEOUT",), dry_run=False)
    assert AiModerationCog._timeout_duration(decision) == expected


def test_action_presentation_uses_human_readable_moderator_copy() -> None:
    assert AiModerationCog._action_presentation("IGNORE")[:2] == ("✅", "No action needed")
    assert AiModerationCog._action_presentation("DELETE_WARN")[:2] == ("🛡️", "Message deleted and warning issued")
