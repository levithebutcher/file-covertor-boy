"""
Main application entry point for Telegram Media Suite.
Runs standalone on Render Web Service or local machine.
"""

import sys
import asyncio
import logging
import signal
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
        logger.info("Telegram client online! Bot is actively listening for updates.")
    except Exception as e:
        logger.error("Failed to start Telegram client: %s", e)

    # Graceful shutdown event
    stop_event = asyncio.Event()

    def signal_handler():
        logger.info("Received termination signal. Shutting down gracefully...")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except (NotImplementedError, RuntimeError):
            # Windows might not support loop.add_signal_handler
            pass

    try:
        await stop_event.wait()
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
