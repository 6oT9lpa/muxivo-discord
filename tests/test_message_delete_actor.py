from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from presentation.cogs.logging_cog import LoggingCog


class _User:
    def __init__(self, user_id: int):
        self.id = user_id
        self.bot = False


class _Guild:
    def __init__(self, entries=()):
        self.entries = entries

    async def audit_logs(self, **_kwargs):
        for entry in self.entries:
            yield entry


class _Channel:
    def __init__(self, channel_id: int):
        self.id = channel_id


class _Message:
    def __init__(self, message_id: int, author: _User, guild=None):
        self.id = message_id
        self.author = author
        self.guild = guild or _Guild()
        self.channel = _Channel(300)


class _AuditEntry:
    def __init__(self, target, user, channel_id: int):
        self.target = target
        self.user = user
        self.created_at = datetime.now(timezone.utc)
        self.extra = type("Extra", (), {"channel": _Channel(channel_id)})()


class _RawDelete:
    def __init__(self, message_id: int):
        self.message_id = message_id
        self.cached_message = None


class _LoggingService:
    def __init__(self):
        self.deleted_by = None

    async def log_message_delete(self, _message, *, deleted_by):
        self.deleted_by = deleted_by


class _Bot:
    def __init__(self, user):
        self.user = user


@pytest.mark.asyncio
async def test_ai_delete_is_attributed_to_omnibot() -> None:
    bot_user = _User(100)
    service = _LoggingService()
    cog = LoggingCog(_Bot(bot_user), service, None, None)
    cog.register_bot_message_deletion(50)

    await cog.on_message_delete(_Message(50, _User(200)))

    assert service.deleted_by is bot_user


@pytest.mark.asyncio
async def test_self_delete_is_attributed_to_message_author() -> None:
    service = _LoggingService()
    author = _User(200)
    cog = LoggingCog(_Bot(_User(100)), service, None, None)

    await cog.on_message_delete(_Message(50, author))

    assert service.deleted_by is author


@pytest.mark.asyncio
async def test_moderator_delete_is_attributed_from_matching_audit_entry() -> None:
    author = _User(200)
    moderator = _User(201)
    service = _LoggingService()
    guild = _Guild([_AuditEntry(author, moderator, channel_id=300)])
    cog = LoggingCog(_Bot(_User(100)), service, None, None)

    await cog.on_message_delete(_Message(50, author, guild))

    assert service.deleted_by is moderator


@pytest.mark.asyncio
async def test_uncached_delete_uses_recent_message_cache() -> None:
    cog = LoggingCog(_Bot(_User(100)), _LoggingService(), None, None)
    message = _Message(50, _User(200))
    cog._log_deleted_message = AsyncMock()

    await cog.on_message(message)
    await cog.on_raw_message_delete(_RawDelete(message.id))

    cog._log_deleted_message.assert_awaited_once_with(message)
