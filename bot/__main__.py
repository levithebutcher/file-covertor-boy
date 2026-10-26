"""
Main application entry point for Telegram Media Suite.
Runs standalone on Render Web Service, VPS, or local machine.
"""

import sys
from pathlib import Path

# Ensure project root is in sys.path so 'python bot/__main__.py' works from anywhere
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import asyncio
import logging
from hydrogram import idle
from bot.core.client import bot_client
from bot.core.web_server import start_web_server

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("MediaConverterBot")


async def main():
    logger.info("==================================================")
    logger.info("   TELEGRAM MEDIA BOT — STANDALONE ENGINE         ")
    logger.info("==================================================")

    # 1. Immediately bind web server to satisfy Render port check (< 50ms)
    runner = None
    try:
        runner = await start_web_server()
    except Exception as e:
        logger.error("Failed to start web server: %s", e)

    # 2. Start Hydrogram Telegram MTProto client
    logger.info("Starting Telegram MTProto client...")
    try:
        await bot_client.start()
        me = await bot_client.get_me()
        logger.info(
            "Telegram client online! Logged in as %s (@%s). Actively listening for updates.",
            me.first_name,
            me.username,
        )

        # 3. Ensure primary owner is initialized in database
        from bot.config import settings
        if settings.primary_owner_id:
            try:
                from bot.database.users import add_user
                await add_user(settings.primary_owner_id, role="owner")
                logger.info("Primary owner ID %d confirmed and authorized in database.", settings.primary_owner_id)
            except Exception as e:
                logger.debug("Notice on owner auto-init: %s", e)
    except Exception as e:
        logger.error("Failed to start Telegram client: %s", e)
        if runner:
            await runner.cleanup()
        return

    # 3. Idle until termination signal (Ctrl+C, SIGINT, SIGTERM)
    try:
        await idle()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        logger.info("Cleaning up services...")
        if bot_client.is_connected:
            await bot_client.stop()
        if runner:
            await runner.cleanup()
        logger.info("Shutdown complete.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
