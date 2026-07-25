import asyncio
import os
import sys

import pytest
import pytest_asyncio

from infrastructure.database import DatabaseManager


# psycopg's async connection layer is incompatible with Windows' Proactor
# loop. Set this before pytest-asyncio creates any fixture loops so optional
# PostgreSQL integration tests run on developer machines as well as CI.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


_RUNTIME_TABLES = """
    messages,
    punishments,
    streamers,
    server_stats,
    roles,
    channel_config,
    user_stats,
    role_panel_messages,
    role_panel_buttons,
    message_logs,
    guild_event_logs,
    server_channel_purposes,
    welcome_config,
    voice_rooms,
    voice_room_members,
    voice_config,
    voice_sessions,
    server_role_purposes,
    activity_synced_roles,
    activity_access_roles,
    activity_access_role_modules,
    activity_synced_role_assignments,
    dev_blog_posts,
    creator_alert_subscriptions
"""


@pytest_asyncio.fixture
async def postgres_test_db() -> DatabaseManager:
    database_url = os.getenv("POSTGRES_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("POSTGRES_TEST_DATABASE_URL is not configured")

    database = DatabaseManager(database_url)
    await database.initialize()
    await database.execute_write(f"TRUNCATE TABLE {_RUNTIME_TABLES} RESTART IDENTITY CASCADE")
    try:
        yield database
    finally:
        await database.close()
