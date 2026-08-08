import asyncio
import sys
from core.product_identity import PRODUCT_NAME
from di import Bootstrap
from infrastructure.logging import get_logger

logger = get_logger(__name__)


async def main():
    logger.info("Starting %s...", PRODUCT_NAME)
    bootstrap = Bootstrap()
    await bootstrap.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (Ctrl+C)")
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
    finally:
        logger.info("Bye!")
