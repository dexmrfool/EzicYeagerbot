from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from bot.config import settings
from bot.telegram.handlers import router as main_router
from bot.telegram.middleware import DeduplicationMiddleware, DatabaseMiddleware


def create_bot_and_dispatcher() -> tuple[Bot, Dispatcher]:
    """Builds and configures the Bot and Dispatcher with middlewares and routers."""
    bot = Bot(
        token=settings.TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
    )

    dp = Dispatcher()

    # Register Middlewares
    dp.message.middleware(DeduplicationMiddleware())
    dp.message.middleware(DatabaseMiddleware())

    # Register Routers
    dp.include_router(main_router)

    return bot, dp
