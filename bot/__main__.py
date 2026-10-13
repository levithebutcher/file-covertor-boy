"""
Main application entry point for Nexus Media Suite.
Controls execution mode (Render Web Service vs Google Colab Worker).
"""

import sys
import asyncio
import logging
import signal
from bot.config import settings
from bot.database.mongo import db_manager
from bot.core.client import bot_client
from bot.core.web_server import start_web_server
from bot.core.handoff import RenderHandoffWatcher, ColabWorkerEngine

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("NexusBot")


async def main():
    # Detect mode from CLI arg or environment variable
    mode = settings.host_mode
    if "--colab" in sys.argv or "--mode=colab" in sys.argv:
        mode = "colab"
    elif "--render" in sys.argv or "--mode=render" in sys.argv:
        mode = "render"

    logger.info("==================================================")
    logger.info("   NEXUS MEDIA SUITE — STARTING BOT ENGINE        ")
    logger.info("   Target Host Mode: %s                            ", mode.upper())
    logger.info("==================================================")

    # Connect to MongoDB Atlas
    await db_manager.connect()

    if mode == "colab":
        # Google Colab Worker Mode
        colab_engine = ColabWorkerEngine()
        await colab_engine.run()
    else:
        # Primary Render Web Service Mode
        # 1. Start HTTP web server for Render keep-alive and health checks
        runner = await start_web_server()

        # 2. Start Hydrogram Telegram MTProto client
        logger.info("Starting Telegram MTProto client...")
        await bot_client.start()
        logger.info("Telegram client online! Bot is actively listening for updates.")

        # 3. Start Handoff Watcher
        watcher = RenderHandoffWatcher()
        watcher_task = asyncio.create_task(watcher.start())

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
            watcher.stop()
            watcher_task.cancel()
            if bot_client.is_connected:
                await bot_client.stop()
            await runner.cleanup()
            await db_manager.close()
            logger.info("Shutdown complete.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
