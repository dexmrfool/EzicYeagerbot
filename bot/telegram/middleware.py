from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from bot.cache.manager import cache_manager
from bot.database.session import async_session_factory
from bot.database.repository import BotRepository
from bot.utils.logging import logger


class DeduplicationMiddleware(BaseMiddleware):
    """Prevents processing duplicate updates if Telegram resends packets."""
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if isinstance(event, Message):
            if cache_manager.is_duplicate_message(event.chat.id, event.message_id):
                logger.debug(f"Duplicate message suppressed: chat={event.chat.id}, msg={event.message_id}")
                return None

        return await handler(event, data)


class DatabaseMiddleware(BaseMiddleware):
    """Injects an async database session and BotRepository into the handler event context."""
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        async with async_session_factory() as session:
            repo = BotRepository(session)
            data["session"] = session
            data["repo"] = repo
            try:
                result = await handler(event, data)
                await session.commit()
                return result
            except Exception as e:
                await session.rollback()
                raise e
