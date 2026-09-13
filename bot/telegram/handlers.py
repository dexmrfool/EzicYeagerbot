import asyncio
import html
import re
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
# MENTION ALL SYSTEM (@all, /all, @everyone, /tagall)
# =====================================================================

ACTIVE_TAGALL_TASKS: set[int] = set()


async def is_mention_authorized(message: Message) -> bool:
    """Checks if the user has permission to mention everyone (Owner, Group Creator, or Admin)."""
    if not message.from_user:
        return False
    user_id = message.from_user.id
    username = (message.from_user.username or "").lower().lstrip("@")

    # 1. Global Owner check
    if (user_id in settings.OWNER_IDS) or (username and username in settings.OWNER_USERNAMES):
        return True

    # 2. Group Admin / Creator check
    if message.chat.type in ("group", "supergroup"):
        try:
            member = await message.chat.get_member(user_id)
            if member.status in ("creator", "administrator"):
                return True
        except Exception:
            pass

    return False


async def process_mention_all(message: Message, repo: BotRepository, raw_text: str):
    """Core logic to broadcast mentions to all group members."""
    if message.chat.type == "private":
        await message.reply("ℹ️ `@all` mentions only work in group chats.")
        return

    chat_id = message.chat.id

    # 1. Verify Permission
    if not await is_mention_authorized(message):
        warning = await message.reply(
            "⚠️ **Permission Denied**: Only group administrators or bot owners can mention everyone."
        )
        await asyncio.sleep(5)
        try:
            await warning.delete()
        except Exception:
            pass
        return

    # Prevent concurrent spam in the same group
    if chat_id in ACTIVE_TAGALL_TASKS:
        await message.reply("⏳ A mention broadcast is already in progress. Use `/cancelall` to stop it.")
        return

    # 2. Extract Message / Prompt
    clean_text = raw_text.strip()
    prompt = re.sub(
        r'^(?:/(?:all|everyone|tagall|mentionall)|@all|@everyone|@tagall)\s*',
        '',
        clean_text,
        flags=re.IGNORECASE
    ).strip()

    reply_to_id = None
    if message.reply_to_message:
        reply_to_id = message.reply_to_message.message_id
        if not prompt and message.reply_to_message.text:
            prompt = "Attention to this message!"

    if not prompt:
        prompt = "Attention everyone!"

    ACTIVE_TAGALL_TASKS.add(chat_id)

    try:
        # 3. Collect Members
        bot_user = await message.bot.get_me()
        seen_ids = {message.from_user.id, bot_user.id}
        members_to_tag = []

        # A. Fetch chat administrators
        admin_count = 0
        try:
            admins = await message.chat.get_administrators()
            for adm in admins:
                if not adm.user.is_bot and adm.user.id not in seen_ids:
                    seen_ids.add(adm.user.id)
                    members_to_tag.append({
                        "user_id": adm.user.id,
                        "first_name": adm.user.first_name or "Admin",
                        "username": adm.user.username
                    })
                    admin_count += 1
        except Exception as ae:
            logger.warning(f"Could not retrieve chat administrators for @all: {ae}")

        # B. Fetch active members from DB
        member_count = 0
        try:
            db_members = await repo.get_group_members(chat_id)
            for dbm in db_members:
                if dbm.telegram_user_id not in seen_ids:
                    seen_ids.add(dbm.telegram_user_id)
                    members_to_tag.append({
                        "user_id": dbm.telegram_user_id,
                        "first_name": dbm.first_name or "Member",
                        "username": dbm.username
                    })
                    member_count += 1
        except Exception as de:
            logger.warning(f"Could not retrieve DB members for @all: {de}")

        if not members_to_tag:
            await message.reply(
                "ℹ️ **No other members found to tag yet.**\n\n"
                "💡 **How to register members:**\n"
                "As soon as group members send any message, sticker, or photo, they are automatically added to the `@all` directory!\n"
                "Use `/members` to view the directory status."
            )
            return

        logger.info(f"Starting @all mention broadcast for {len(members_to_tag)} members ({admin_count} admins, {member_count} members) in chat {chat_id} by user {message.from_user.id}")

        # 4. Broadcast in batches of 5 members
        batch_size = 5
        total_batches = (len(members_to_tag) + batch_size - 1) // batch_size
        safe_prompt = html.escape(prompt)

        for idx in range(0, len(members_to_tag), batch_size):
            if chat_id not in ACTIVE_TAGALL_TASKS:
                logger.info(f"Mention broadcast in chat {chat_id} stopped.")
                break

            batch = members_to_tag[idx:idx + batch_size]
            mention_links = []
            for m in batch:
                safe_name = html.escape(m["first_name"])
                mention_links.append(f'<a href="tg://user?id={m["user_id"]}">{safe_name}</a>')

            batch_num = (idx // batch_size) + 1
            body = f"📢 <b>{safe_prompt}</b>\n\n👥 " + " • ".join(mention_links)
            if total_batches > 1:
                body += f"\n<i>({batch_num}/{total_batches})</i>"
            if idx == 0 and member_count == 0:
                body += "\n\n<i>💡 Note: Regular members are automatically added to @all as soon as they send a message or sticker.</i>"

            try:
                await message.bot.send_message(
                    chat_id=chat_id,
                    text=body,
                    parse_mode="HTML",
                    reply_to_message_id=reply_to_id or message.message_id
                )
            except Exception as se:
                logger.error(f"Error sending mention batch {batch_num} in {chat_id}: {se}")

            # 1.5s interval to avoid flood wait
            if idx + batch_size < len(members_to_tag):
                await asyncio.sleep(1.5)

    finally:
        ACTIVE_TAGALL_TASKS.discard(chat_id)


@router.message(Command("all", "everyone", "tagall", "mentionall"))
async def handle_mention_command(message: Message, repo: BotRepository):
    """Command-based mention all (/all <message>, /everyone <message>, /tagall <message>)."""
    await process_mention_all(message, repo, message.text or "")


@router.message(Command("cancelall", "stopall", "tagstop"))
async def handle_cancel_mention(message: Message):
    """Stops an ongoing @all broadcast."""
    if not await is_mention_authorized(message):
        return
    chat_id = message.chat.id
    if chat_id in ACTIVE_TAGALL_TASKS:
        ACTIVE_TAGALL_TASKS.discard(chat_id)
        await message.reply("🛑 **Mention broadcast stopped.**")
    else:
        await message.reply("ℹ️ No mention broadcast is currently active.")


@router.message(Command("members", "tagstatus", "taglist"))
async def handle_members_status(message: Message, repo: BotRepository):
    """Displays all known members registered in the @all mention directory."""
    if message.chat.type == "private":
        await message.reply("ℹ️ `/members` only works in group chats.")
        return

    chat_id = message.chat.id
    admins = []
    try:
        admins = await message.chat.get_administrators()
    except Exception:
        pass

    admin_users = [a.user for a in admins if not a.user.is_bot]
    admin_ids = {a.id for a in admin_users}

    db_members = await repo.get_group_members(chat_id)
    regular_members = [m for m in db_members if m.telegram_user_id not in admin_ids]

    total_taggable = len(admin_users) + len(regular_members)

    await message.reply(
        f"👥 **Group Mention Directory Status**\n\n"
        f"• **Total Taggable Users:** {total_taggable}\n"
        f"• **Administrators (Live):** {len(admin_users)}\n"
        f"• **Active Members Indexed:** {len(regular_members)}\n\n"
        f"💡 *Every member who sends any message or sticker in this group is automatically included in `@all`!*"
    )


# =====================================================================
# NATURAL MESSAGE PIPELINE (Translation + Butler AI)
# =====================================================================

@router.message(F.text)
async def handle_natural_message(message: Message, repo: BotRepository):
    """
    Core natural language pipeline.
    Zero commands required. Automatically handles:
    1. @all / @everyone mentions
    2. Butler AI conversational response (if enabled and addressed)
    3. Automatic multilingual translation (if foreign language detected)
    """
    # 1. Ignore own messages or messages from other bots to prevent infinite loops
    if not message.from_user or message.from_user.is_bot:
        return

    text = message.text.strip()
    if not text:
        return

    # Check for @all or @everyone mentions in natural text
    clean_lower = text.lower()
    if clean_lower.startswith(("@all", "@everyone", "@tagall")):
        await process_mention_all(message, repo, text)
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
