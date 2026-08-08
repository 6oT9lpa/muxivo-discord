from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from infrastructure.database.connection import DatabaseManager
from infrastructure.logging import get_logger

logger = get_logger(__name__)

FLAG_COLUMNS: dict[str, dict[str, int]] = {
    "messages": {"deleted": 0, "edited": 0, "ai_flagged": 0},
    "punishments": {"active": 1, "is_active": 1},
    "streamers": {"active": 1},
    "roles": {"is_auto_assign": 0, "is_public": 1},
    "channel_config": {"is_ai_whitelisted": 0, "welcome_enabled": 1},
    "role_panel_messages": {"is_active": 1},
    "activity_synced_roles": {"is_admin": 0, "managed": 0, "mentionable": 0},
    "activity_access_roles": {"is_builtin": 0},
    "creator_alert_subscriptions": {"active": 1},
}


async def main() -> None:
    args = parse_args()
    database = DatabaseManager(args.postgres)
    await database.initialize()
    try:
        changed = await normalize_flags(database)
        logger.info("PostgreSQL flag columns normalized changed=%s", changed)
        print(f"Normalized PostgreSQL flag columns: {changed}")
    finally:
        await database.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize legacy PostgreSQL boolean flags to Muxivo Discord numeric flags.")
    parser.add_argument("--postgres", required=True, help="PostgreSQL URL.")
    return parser.parse_args()


async def normalize_flags(database: DatabaseManager) -> int:
    changed = 0
    for table, columns in FLAG_COLUMNS.items():
        for column, default in columns.items():
            if not await is_boolean_column(database, table, column):
                continue
            await convert_boolean_column(database, table, column, default)
            changed += 1
            logger.info("Converted PostgreSQL flag column table=%s column=%s default=%s", table, column, default)
    return changed


async def is_boolean_column(database: DatabaseManager, table: str, column: str) -> bool:
    row = await database.fetch_one(
        """
        SELECT data_type
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = ?
          AND column_name = ?
        LIMIT 1
        """,
        (table, column),
    )
    return bool(row and row["data_type"] == "boolean")


async def convert_boolean_column(database: DatabaseManager, table: str, column: str, default: int) -> None:
    await database.execute_write(f'ALTER TABLE "{table}" ALTER COLUMN "{column}" DROP DEFAULT')
    await database.execute_write(
        f"""
        ALTER TABLE "{table}"
        ALTER COLUMN "{column}" TYPE BIGINT
        USING CASE
            WHEN "{column}" IS TRUE THEN 1
            WHEN "{column}" IS FALSE THEN 0
            ELSE NULL
        END
        """
    )
    await database.execute_write(f'ALTER TABLE "{table}" ALTER COLUMN "{column}" SET DEFAULT {default}')


if __name__ == "__main__":
    asyncio.run(main())
