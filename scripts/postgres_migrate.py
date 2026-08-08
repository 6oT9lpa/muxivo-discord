"""Apply PostgreSQL migrations before starting Muxivo Discord services."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from infrastructure.config import get_config
from infrastructure.database import DatabaseManager
from infrastructure.logging import get_logger


logger = get_logger(__name__)


async def main() -> None:
    """Apply Alembic migrations, then ensure runtime PostgreSQL tables exist."""
    database = DatabaseManager(get_config().database_url)
    try:
        await database.run_migrations()
        await database.initialize()
        logger.info("PostgreSQL migration stage completed")
    finally:
        await database.close()


if __name__ == "__main__":
    asyncio.run(main())
