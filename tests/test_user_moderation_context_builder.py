from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from application.services.user_moderation_context_builder import UserModerationContextBuilder


class _Punishments:
    async def list_for_user(self, *_args, **_kwargs):
        now = datetime.now(timezone.utc)
        return [{"type": "timeout", "created_at": now - timedelta(days=2)}, {"type": "ban", "created_at": now - timedelta(days=40)}]


class _Events:
    async def count_ai_deleted_messages(self, *_args):
        return 1


@pytest.mark.asyncio
async def test_context_is_guild_scoped_and_windowed() -> None:
    member = SimpleNamespace(created_at=datetime.now(timezone.utc) - timedelta(days=90), joined_at=datetime.now(timezone.utc) - timedelta(days=10))
    context = await UserModerationContextBuilder(_Punishments(), _Events()).build(member, 1, 2, 30)
    assert context.account_age_days == 90
    assert context.guild_membership_days == 10
    assert context.punishments.total_in_window == 2
    assert context.punishments.timeouts_in_window == 1
    assert context.punishments.bans_in_window == 0
    assert context.punishments.ai_deleted_messages_in_window == 1


def test_weighted_escalation_score_weights_severity_and_recency() -> None:
    now = datetime.now(timezone.utc)
    builder = UserModerationContextBuilder(_Punishments(), _Events())

    score = builder._weighted_escalation_score(
        [
            {"type": "warn", "created_at": now},
            {"type": "timeout", "created_at": now},
            {"type": "kick", "created_at": now},
            {"type": "ban", "created_at": now},
            {"type": "warn", "created_at": now - timedelta(days=30)},
        ],
        now,
        half_life_days=30,
    )

    assert score == 10.5
