from __future__ import annotations

import argparse
import asyncio
import sqlite3
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from infrastructure.database.connection import DatabaseManager
from infrastructure.logging import get_logger

logger = get_logger(__name__)

TABLES_IN_COPY_ORDER = (
    "messages",
    "punishments",
    "streamers",
    "server_stats",
    "roles",
    "channel_config",
    "user_stats",
    "role_panel_messages",
    "role_panel_buttons",
    "message_logs",
    "guild_event_logs",
    "server_channel_purposes",
    "welcome_config",
    "voice_rooms",
    "voice_room_members",
    "voice_config",
    "voice_sessions",
    "server_role_purposes",
    "activity_synced_roles",
    "activity_access_roles",
    "activity_access_role_modules",
    "activity_synced_role_assignments",
    "dev_blog_posts",
    "creator_alert_subscriptions",
)


async def main() -> None:
    args = parse_args()
    sqlite_path = Path(args.sqlite).resolve()
    if not sqlite_path.exists():
        raise FileNotFoundError(f"SQLite database not found: {sqlite_path}")

    postgres = DatabaseManager(args.postgres)
    await postgres.run_migrations()
    await postgres.initialize()
    try:
        if args.truncate:
            await truncate_postgres(postgres)
        copied = await copy_sqlite_to_postgres(sqlite_path, postgres)
        await reset_sequences(postgres)
        logger.info("SQLite to PostgreSQL migration completed copied_rows=%s", copied)
        print(f"Migration completed. Copied rows: {copied}")
    finally:
        await postgres.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate Muxivo Discord data from SQLite to PostgreSQL.")
    parser.add_argument("--sqlite", default="data/nexsusguard.db", help="Path to source SQLite database.")
    parser.add_argument("--postgres", required=True, help="Target PostgreSQL URL.")
    parser.add_argument("--truncate", action="store_true", help="Delete target table data before copy.")
    return parser.parse_args()


async def truncate_postgres(postgres: DatabaseManager) -> None:
    table_list = ", ".join(TABLES_IN_COPY_ORDER)
    await postgres.execute_write(f"TRUNCATE TABLE {table_list} RESTART IDENTITY CASCADE")
    logger.info("PostgreSQL target tables truncated")


async def copy_sqlite_to_postgres(sqlite_path: Path, postgres: DatabaseManager) -> int:
    source = sqlite3.connect(sqlite_path)
    source.row_factory = sqlite3.Row
    total = 0
    try:
        for table in TABLES_IN_COPY_ORDER:
            if not sqlite_table_exists(source, table):
                logger.info("Skip missing SQLite table=%s", table)
                continue
            rows = source.execute(f'SELECT * FROM "{table}"').fetchall()
            if not rows:
                logger.info("Skip empty SQLite table=%s", table)
                continue

            target_columns = await load_postgres_columns(postgres, table)
            boolean_columns = {
                name for name, data_type in target_columns.items()
                if data_type == "boolean"
            }
            copied = await copy_table_rows(postgres, table, rows, target_columns, boolean_columns)
            total += copied
            logger.info("Copied table=%s rows=%s", table, copied)
        return total
    finally:
        source.close()


def sqlite_table_exists(source: sqlite3.Connection, table: str) -> bool:
    row = source.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


async def load_postgres_columns(postgres: DatabaseManager, table: str) -> dict[str, str]:
    rows = await postgres.fetch_all(
        """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = ?
        ORDER BY ordinal_position
        """,
        (table,),
    )
    return {row["column_name"]: row["data_type"] for row in rows}


async def copy_table_rows(
    postgres: DatabaseManager,
    table: str,
    rows: list[sqlite3.Row],
    target_columns: dict[str, str],
    boolean_columns: set[str],
) -> int:
    copied = 0
    for row in rows:
        payload = {
            key: normalize_value(key, row[key], boolean_columns)
            for key in row.keys()
            if key in target_columns
        }
        if not payload:
            continue
        columns = tuple(payload.keys())
        column_sql = ", ".join(f'"{column}"' for column in columns)
        placeholders = ", ".join("?" for _ in columns)
        query = f'INSERT INTO "{table}" ({column_sql}) VALUES ({placeholders}) ON CONFLICT DO NOTHING'
        result = await postgres.execute_write(query, tuple(payload.values()))
        copied += max(result["rowcount"] or 0, 0)
    return copied


def normalize_value(column: str, value: Any, boolean_columns: set[str]) -> Any:
    if value is None:
        return None
    if column in boolean_columns:
        return bool(value)
    return value


async def reset_sequences(postgres: DatabaseManager) -> None:
    for table in TABLES_IN_COPY_ORDER:
        if not await postgres.fetch_one(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = ?
              AND column_name = 'id'
            LIMIT 1
            """,
            (table,),
        ):
            continue
        await postgres.execute_write(
            f"""
            SELECT setval(
                pg_get_serial_sequence('{table}', 'id'),
                GREATEST(COALESCE((SELECT MAX(id) FROM "{table}"), 1), 1),
                true
            )
            """
        )
    logger.info("PostgreSQL sequences reset")


if __name__ == "__main__":
    asyncio.run(main())
