"""
Lightweight asynchronous web server for Render Free port binding and health checks.
Accepts all HTTP methods (*), returning immediate 200 OK.
"""

import time
import logging
from aiohttp import web
from bot.config import settings

logger = logging.getLogger(__name__)

start_timestamp = time.time()


async def health_handler(request: web.Request) -> web.Response:
    """Health check endpoint required by Render web services and external cron pingers."""
    from bot.core.client import bot_client
    uptime = time.time() - start_timestamp
    tg_online = getattr(bot_client, "is_connected", False)

    return web.json_response({
        "status": "healthy",
        "service": "telegram_media_suite",
        "telegram_online": tg_online,
        "uptime_seconds": round(uptime, 2),
    })


def create_web_app() -> web.Application:
    app = web.Application()
    # Accept any HTTP method (GET, POST, HEAD, OPTIONS) on common ping paths
    for path in ["/", "/health", "/ping", "/status"]:
        app.router.add_route("*", path, health_handler)
    return app


async def start_web_server():
    """Start the HTTP server on configured port."""
    app = create_web_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=settings.port)
    await site.start()
    logger.info("Health check server listening on http://0.0.0.0:%d/health", settings.port)
    return runner
