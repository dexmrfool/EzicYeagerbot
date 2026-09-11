from datetime import datetime, timezone, timedelta
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from bot.config import settings
from bot.telegram.permissions import IsOwnerFilter
from bot.database.repository import BotRepository
from bot.cache.manager import cache_manager
from bot.translation.detector import language_detector
from bot.translation.translator import translator
from bot.butler.intent import intent_classifier
from bot.butler.brain import butler_brain
from bot.utils.text import format_translation_reply
from bot.utils.logging import logger

router = Router(name="main_router")

# Track startup timestamp to discard all historical/backlog messages
BOT_STARTUP_TIME = datetime.now(timezone.utc)

def set_startup_time():
    global BOT_STARTUP_TIME
    BOT_STARTUP_TIME = datetime.now(timezone.utc)
    logger.info(f"Bot startup timestamp initialized to {BOT_STARTUP_TIME.isoformat()}")


# =====================================================================
# INVISIBLE OWNER CONTROLS (Zero visible commands for normal users)
# Unique stealth commands: /ezicon (or /awaken, /arise) & /ezicoff (or /slumber, /sleep)
# =====================================================================

@router.message(Command("ezicon", "awaken", "arise", "enable"), IsOwnerFilter())
async def handle_owner_enable(message: Message, repo: BotRepository):
    """
    Invisible stealth activation command (/ezicon, /awaken, /arise).
    Silently activates Butler AI for this specific group.
    """
    chat_id = message.chat.id
    chat_title = message.chat.title or "Private Chat"

    await repo.set_butler_state(chat_id, enabled=True)
    cache_manager.invalidate_group(chat_id)
    logger.info(f"Owner {message.from_user.id} silently ENABLED Butler in chat {chat_id} ('{chat_title}')")

    # Attempt to silently remove the command message so other users see no trace
    try:
        await message.delete()
    except Exception:
        pass

    # Send silent private confirmation to the owner in DM
    try:
        if message.chat.type != "private":
            await message.bot.send_message(
                chat_id=message.from_user.id,
                text=f"🤫 **Butler AI Awakened (`/ezicon`)**\nGroup: **{chat_title}** (`{chat_id}`)\nButler AI is now active and conversational."
            )
    except Exception:
        pass


@router.message(Command("ezicoff", "slumber", "sleep", "disable"), IsOwnerFilter())
async def handle_owner_disable(message: Message, repo: BotRepository):
    """
    Invisible stealth deactivation command (/ezicoff, /slumber, /sleep).
    Silently deactivates Butler AI for this specific group.
    """
    chat_id = message.chat.id
    chat_title = message.chat.title or "Private Chat"

    await repo.set_butler_state(chat_id, enabled=False)
    cache_manager.invalidate_group(chat_id)
    logger.info(f"Owner {message.from_user.id} silently DISABLED Butler in chat {chat_id} ('{chat_title}')")

    try:
        await message.delete()
    except Exception:
        pass

    try:
        if message.chat.type != "private":
            await message.bot.send_message(
                chat_id=message.from_user.id,
                text=f"🤫 **Butler AI Slumbered (`/ezicoff`)**\nGroup: **{chat_title}** (`{chat_id}`)\nTranslation remains active. On-demand /ai still available."
            )
    except Exception:
        pass


# =====================================================================
# EXPLICIT ON-DEMAND AI COMMANDS (/ai, /ask)
# =====================================================================

@router.message(Command("ai", "ask"))
async def handle_ai_command(message: Message, repo: BotRepository):
    """
    On-demand AI query command: /ai <prompt> or /ask <prompt>.
    Also supports replying to any message with /ai (e.g. /ai explain this).
    """
    if not message.from_user or message.from_user.is_bot:
        return

    # Extract query text after /ai or /ask
    command_parts = (message.text or "").split(maxsplit=1)
    prompt = command_parts[1].strip() if len(command_parts) > 1 else ""

    # If replying to another message, attach the referenced context
    if message.reply_to_message and message.reply_to_message.text:
        replied_text = message.reply_to_message.text.strip()
        if prompt:
            prompt = f"{prompt}\n\n[Referenced Message]:\n{replied_text}"
        else:
            prompt = replied_text

    if not prompt:
        await message.reply("💡 **Ask me anything:**\nUse `/ai <your question>` or reply to a message with `/ai`!")
        return

    chat_id = message.chat.id
    user_name = message.from_user.first_name or message.from_user.username or "Friend"

    # Evaluate whether live search is needed
    _, needs_search = intent_classifier.should_butler_respond(
        text=prompt,
        is_reply_to_bot=True,
        is_bot_mentioned=True,
        is_private_chat=True
    )

    group = cache_manager.get_cached_group(chat_id)
    target_lang = group.target_language if group else settings.DEFAULT_TARGET_LANGUAGE

    try:
        await message.bot.send_chat_action(chat_id=chat_id, action="typing")
        reply_text = await butler_brain.generate_response(
            repo=repo,
            group_id=chat_id,
            user_id=message.from_user.id,
            user_name=user_name,
            user_message=prompt,
            requires_web_search=needs_search,
            group_target_lang=target_lang
        )
        if reply_text:
            await message.reply(reply_text)
    except Exception as e:
        logger.error(f"Error handling /ai command: {e}")


# =====================================================================
# NATURAL MESSAGE PIPELINE (Translation + Butler AI)
# =====================================================================

@router.message(F.text)
async def handle_natural_message(message: Message, repo: BotRepository):
    """
    Core natural language pipeline.
    Zero commands required. Automatically handles:
    1. Butler AI conversational response (if enabled and addressed)
    2. Automatic multilingual translation (if foreign language detected)
    """
    # 1. Ignore own messages or messages from other bots to prevent infinite loops
    if not message.from_user or message.from_user.is_bot:
        return

    text = message.text.strip()
    if not text:
        return

    # Ignore slash commands so we don't translate slash commands
    if text.startswith("/"):
        return

    # Drop stale or backlog messages - strictly process fresh, real-time messages only
    now = datetime.now(timezone.utc)
    msg_date = message.date
    if msg_date.tzinfo is None:
        msg_date = msg_date.replace(tzinfo=timezone.utc)

    if msg_date < (BOT_STARTUP_TIME - timedelta(seconds=120)):
        logger.debug(f"Ignoring historical message {message.message_id} from before startup ({msg_date})")
        return

    if (now - msg_date) > timedelta(seconds=120):
        logger.debug(f"Ignoring stale message {message.message_id} sent {(now - msg_date).total_seconds():.1f}s ago")
        return

    chat_id = message.chat.id
    is_private = (message.chat.type == "private")

    # 2. Retrieve group configuration (with fast in-memory cache)
    group = cache_manager.get_cached_group(chat_id)
    if not group:
        group = await repo.get_or_create_group(chat_id, message.chat.title)
        cache_manager.set_cached_group(chat_id, group)

    target_lang = group.target_language or settings.DEFAULT_TARGET_LANGUAGE

    # 3. Check if Butler AI is enabled and should respond
    bot_user = await message.bot.get_me()
    is_reply_to_bot = bool(
        message.reply_to_message and
        message.reply_to_message.from_user and
        message.reply_to_message.from_user.id == bot_user.id
    )
    is_bot_mentioned = bool(
        bot_user.username and f"@{bot_user.username.lower()}" in text.lower()
    )

    is_addressed_by_name = intent_classifier.is_addressed_by_name(text)
    is_directly_addressed = bool(is_reply_to_bot or is_bot_mentioned or is_addressed_by_name)

    # Butler responds if:
    # 1. Butler is enabled for group, OR
    # 2. In private DM, OR
    # 3. User directly addressed the bot by name ('ezic', 'yeager'), @mention, or reply!
    if group.butler_enabled or is_private or is_directly_addressed:
        should_respond, needs_search = intent_classifier.should_butler_respond(
            text=text,
            is_reply_to_bot=is_reply_to_bot,
            is_bot_mentioned=is_bot_mentioned,
            is_private_chat=is_private
        )

        if should_respond:
            user_name = message.from_user.first_name or message.from_user.username or "Friend"
            try:
                # Send typing action for natural human feel
                await message.bot.send_chat_action(chat_id=chat_id, action="typing")
                reply_text = await butler_brain.generate_response(
                    repo=repo,
                    group_id=chat_id,
                    user_id=message.from_user.id,
                    user_name=user_name,
                    user_message=text,
                    requires_web_search=needs_search,
                    group_target_lang=target_lang
                )
                if reply_text:
                    await message.reply(reply_text)
                    return
            except Exception as be:
                logger.error(f"Error handling Butler AI response: {be}")

    # 4. Automatic Multilingual Translation
    if group.translation_enabled:
        should_trans, lang_hint = language_detector.should_translate(text, target_lang=target_lang)

        if should_trans:
            try:
                translated = await translator.translate(
                    text=text,
                    target_lang=target_lang,
                    detected_lang=lang_hint,
                    preserve_profanity=group.profanity_preservation
                )
                if translated:
                    formatted = format_translation_reply(translated, source_lang=lang_hint, target_lang=target_lang)
                    await message.reply(formatted)
                    logger.info(
                        f"Auto-translated message {message.message_id} in {chat_id}: "
                        f"'{text[:30]}...' -> '{translated[:30]}...'"
                    )
            except Exception as te:
                logger.error(f"Error in automatic translation: {te}")
