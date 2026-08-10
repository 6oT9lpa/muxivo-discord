from unittest.mock import AsyncMock

import pytest
from activity.server.services.stats_service import ActivityStatsService


@pytest.mark.asyncio
async def test_activity_server_stats_keeps_module_access_before_shared_snapshot() -> None:
    service = ActivityStatsService.__new__(ActivityStatsService)
    access = AsyncMock()
    service._access_service = access
    service.get_server_stats_snapshot = AsyncMock(return_value={"summary": {"period_days": 30}})

    result = await service.get_server_stats(123456789, 30, "activity-token")

    access.ensure_module_access.assert_awaited_once_with(
        "activity-token", "123456789", "server-stats"
    )
    service.get_server_stats_snapshot.assert_awaited_once_with(123456789, 30)
    assert result == {"summary": {"period_days": 30}}


@pytest.mark.asyncio
async def test_shared_snapshot_reuses_existing_stats_queries() -> None:
    service = ActivityStatsService.__new__(ActivityStatsService)
    service._query_server_stats = AsyncMock(return_value={"period_days": 14})
    service._query_channel_stats = AsyncMock(return_value=[{"channel_id": 1}])
    service._query_hourly_stats = AsyncMock(return_value=[{"hour": 0, "count": 2}])
    service._query_daily_stats = AsyncMock(return_value=[{"date": "2026-08-10", "count": 3}])

    result = await service.get_server_stats_snapshot(987654321, 45)

    service._query_server_stats.assert_awaited_once_with(987654321, 45)
    service._query_channel_stats.assert_awaited_once_with(987654321, 45)
    service._query_hourly_stats.assert_awaited_once_with(987654321, 45)
    service._query_daily_stats.assert_awaited_once_with(987654321, 30)
    assert result == {
        "summary": {"period_days": 14},
        "channels": [{"channel_id": 1}],
        "hourly": [{"hour": 0, "count": 2}],
        "daily": [{"date": "2026-08-10", "count": 3}],
    }
