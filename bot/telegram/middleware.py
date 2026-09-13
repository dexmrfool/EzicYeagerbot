from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message, ChatMemberUpdated, TelegramObject
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
    """Injects an async database session and BotRepository into the handler event context, and auto-indexes members."""
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

            # Universal Group Member Auto-Indexer
            # Records anyone who sends ANY message, sticker, media, command, reply, or forward in a group
            if isinstance(event, Message) and event.chat.type in ("group", "supergroup"):
                chat_id = event.chat.id
                users_to_index = []

                if event.from_user and not event.from_user.is_bot:
                    users_to_index.append(event.from_user)

                if event.reply_to_message and event.reply_to_message.from_user and not event.reply_to_message.from_user.is_bot:
                    users_to_index.append(event.reply_to_message.from_user)

                if event.forward_from and not event.forward_from.is_bot:
                    users_to_index.append(event.forward_from)

                if event.new_chat_members:
                    for ncm in event.new_chat_members:
                        if not ncm.is_bot:
                            users_to_index.append(ncm)

                for u in users_to_index:
                    try:
                        await repo.upsert_group_member(
                            telegram_group_id=chat_id,
                            telegram_user_id=u.id,
                            username=u.username,
                            first_name=u.first_name or "Member"
                        )
                    except Exception:
                        pass

            elif isinstance(event, ChatMemberUpdated) and event.chat.type in ("group", "supergroup"):
                if event.new_chat_member and event.new_chat_member.user and not event.new_chat_member.user.is_bot:
                    u = event.new_chat_member.user
                    try:
                        await repo.upsert_group_member(
                            telegram_group_id=event.chat.id,
                            telegram_user_id=u.id,
                            username=u.username,
                            first_name=u.first_name or "Member"
                        )
                    except Exception:
                        pass

            try:
                result = await handler(event, data)
                await session.commit()
                return result
            except Exception as e:
                await session.rollback()
                raise e
