from datetime import datetime, timezone

import pytest

from application.services.member_join_history_service import MemberJoinHistoryService


class _Repository:
    def __init__(self) -> None:
        self.calls: list[tuple[int, int, datetime]] = []

    async def record_join(self, guild_id: int, user_id: int, joined_at: datetime) -> bool:
        self.calls.append((guild_id, user_id, joined_at))
        return len(self.calls) == 1

    async def record_leave(self, guild_id: int, user_id: int, left_at: datetime) -> bool:
        self.calls.append((guild_id, user_id, left_at))
        return True


@pytest.mark.asyncio
async def test_records_first_join_and_rejoin() -> None:
    repository = _Repository()
    service = MemberJoinHistoryService(repository)
    joined_at = datetime(2026, 7, 23, tzinfo=timezone.utc)

    assert await service.record_join(10, 20, joined_at)
    assert not await service.record_join(10, 20, joined_at)
    assert repository.calls == [(10, 20, joined_at), (10, 20, joined_at)]


@pytest.mark.asyncio
async def test_skips_join_when_discord_does_not_provide_timestamp() -> None:
    repository = _Repository()

    assert not await MemberJoinHistoryService(repository).record_join(10, 20, None)
    assert repository.calls == []


@pytest.mark.asyncio
async def test_records_leave_with_explicit_utc_timestamp() -> None:
    repository = _Repository()
    left_at = datetime(2026, 7, 24, tzinfo=timezone.utc)

    assert await MemberJoinHistoryService(repository).record_leave(10, 20, left_at)
    assert repository.calls == [(10, 20, left_at)]


@pytest.mark.asyncio
async def test_normalizes_lifecycle_timestamps_to_utc() -> None:
    repository = _Repository()
    local_time = datetime.fromisoformat("2026-07-24T18:00:00+03:00")

    await MemberJoinHistoryService(repository).record_leave(10, 20, local_time)

    assert repository.calls[0][2] == datetime(2026, 7, 24, 15, 0, tzinfo=timezone.utc)
