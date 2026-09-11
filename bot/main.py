import asyncio
import os
import signal
import sys
from aiohttp import web
from bot.config import settings
from bot.database.migrations import init_db
from bot.database.session import engine
from bot.telegram.client import create_bot_and_dispatcher
from bot.telegram.handlers import set_startup_time
from bot.utils.logging import logger


async def start_health_server(port: int) -> web.AppRunner:
    """Lightweight HTTP server for container/VPS health checks."""
    app = web.Application()

    async def health_check(request):
        return web.Response(text="OK - Multilingual Butler Bot is running live", status=200)

    app.add_routes([web.get("/", health_check), web.get("/health", health_check)])
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Health-check HTTP server running on port {port}")
    return runner


async def main():
    logger.info("Starting Telegram Multilingual Translator + Butler AI Bot...")

    if not settings.TELEGRAM_BOT_TOKEN:
        logger.error(
            "TELEGRAM_BOT_TOKEN is missing! Please configure your bot token in the .env file."
        )
        sys.exit(1)

    # 1. Initialize Database & Seed Glossaries
    try:
        await init_db()
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        sys.exit(1)

    # 2. Build Telegram Client
    bot, dp = create_bot_and_dispatcher()

    # 3. Start Health Server
    runner = None
    try:
        runner = await start_health_server(settings.PORT)
    except Exception as e:
        logger.warning(f"Could not start health check web server ({e}). Continuing bot execution...")

    # 4. Verify Bot Credentials
    bot_info = await bot.get_me()
    logger.info(f"Connected to Telegram as @{bot_info.username} (ID: {bot_info.id})")
    logger.info(f"Authorized Owner IDs: {settings.OWNER_IDS} | Usernames: {settings.OWNER_USERNAMES}")
    logger.info("Bot is active and listening for group updates.")

    # 5. Flush pending updates and record exact startup time
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Cleared Telegram pending/backlog update queue.")
    except Exception as we:
        logger.warning(f"Could not drop webhook pending updates: {we}")

    set_startup_time()

    # 6. Start Polling with Graceful Shutdown
    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            drop_pending_updates=True
        )
    except (asyncio.CancelledError, KeyboardInterrupt):
        logger.info("Shutdown signal received.")
    finally:
        logger.info("Cleaning up and closing connections...")
        if runner:
            await runner.cleanup()
        await bot.session.close()
        await engine.dispose()
        logger.info("Bot shutdown complete.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
