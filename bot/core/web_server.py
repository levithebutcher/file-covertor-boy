"""
Lightweight asynchronous web server for Render Free port binding and health checks.
"""

import time
import logging
from aiohttp import web
from bot.config import settings
from bot.database.mongo import db_manager

logger = logging.getLogger(__name__)

start_timestamp = time.time()


async def health_handler(request: web.Request) -> web.Response:
    """Health check endpoint required by Render web services."""
    uptime = time.time() - start_timestamp
    return web.json_response({
        "status": "healthy",
        "service": "nexus_media_suite",
        "host_mode": settings.host_mode,
        "database_connected": db_manager.is_connected,
        "uptime_seconds": round(uptime, 2),
    })


def create_web_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", health_handler)
    app.router.add_get("/health", health_handler)
    return app


async def start_web_server():
    """Start the HTTP server on configured port."""
    app = create_web_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=settings.port)
    await site.start()
    logger.info("Render health web server listening on http://0.0.0.0:%d/health", settings.port)
    return runner
