from aiogram.filters import BaseFilter
from aiogram.types import Message
from bot.config import settings
from bot.utils.logging import logger


class IsOwnerFilter(BaseFilter):
    """
    Invisible Owner Security Filter.
    Ensures hidden commands (/enable, /disable) only match if sent by an authorized OWNER_ID or OWNER_USERNAME.
    If sent by anyone else, the filter returns False and the bot silently ignores it.
    """
    async def __call__(self, message: Message) -> bool:
        if not message.from_user:
            return False

        user_id = message.from_user.id
        username = (message.from_user.username or "").lower().lstrip("@")

        is_owner = (user_id in settings.OWNER_IDS) or (username and username in settings.OWNER_USERNAMES)

        if not is_owner and message.text and message.text.strip().lower().startswith(("/enable", "/disable")):
            # Log security attempt internally without exposing error to user
            logger.warning(
                f"Unauthorized hidden command attempt from user_id={user_id} (@{username}) "
                f"in chat_id={message.chat.id}: '{message.text}'"
            )

        return is_owner
