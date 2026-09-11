from aiogram.filters import BaseFilter
from aiogram.types import Message
from bot.config import settings
from bot.utils.logging import logger


class IsOwnerFilter(BaseFilter):
    """
    Invisible Owner Security Filter.
    Ensures hidden commands (/ezicon, /ezicoff, /enable, /disable) match if sent by:
    1. An authorized OWNER_ID or OWNER_USERNAME from settings.
    2. A chat Creator / Administrator in group chats.
    If sent by anyone else, the filter returns False and the bot silently ignores it.
    """
    async def __call__(self, message: Message) -> bool:
        if not message.from_user:
            return False

        user_id = message.from_user.id
        username = (message.from_user.username or "").lower().lstrip("@")

        is_owner = (user_id in settings.OWNER_IDS) or (username and username in settings.OWNER_USERNAMES)

        # Allow group creators or administrators to control the bot in their group
        if not is_owner and message.chat.type in ("group", "supergroup"):
            try:
                member = await message.chat.get_member(user_id)
                if member.status in ("creator", "administrator"):
                    is_owner = True
            except Exception:
                pass

        if not is_owner and message.text and message.text.strip().lower().startswith(
            ("/enable", "/disable", "/ezicon", "/ezicoff", "/awaken", "/slumber", "/arise", "/sleep")
        ):
            logger.warning(
                f"Unauthorized stealth command attempt from user_id={user_id} (@{username}) "
                f"in chat_id={message.chat.id}: '{message.text}'"
            )

        return is_owner
