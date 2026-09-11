"""
Telegram integration package: handlers, client, middleware, and permissions.
"""
from bot.telegram.client import create_bot_and_dispatcher
from bot.telegram.permissions import IsOwnerFilter

__all__ = ["create_bot_and_dispatcher", "IsOwnerFilter"]
