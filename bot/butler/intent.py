import re
from typing import Tuple
from bot.config import settings


class IntentClassifier:
    """Classifies incoming messages to determine if Butler AI should engage and if web search is needed."""

    NEWS_PATTERNS = [
        re.compile(r'\b(?:latest|new|recent|upcoming)\b.*?\b(?:news|chapter|episode|update|patch|season|release|leak|spoilers?)\b', re.IGNORECASE),
        re.compile(r'\b(?:when\s+(?:is|will|does))\b.*?\b(?:release|come\s+out|air|drop)\b', re.IGNORECASE),
        re.compile(r'\b(?:what\s+happened)\b.*?\b(?:with|to|today|recently|in)\b', re.IGNORECASE),
        re.compile(r'\b(?:who\s+won|score|match\s+result)\b', re.IGNORECASE),
        re.compile(r'\b(?:news|update|announcement)\b', re.IGNORECASE)
    ]

    QUESTION_WORDS = [
        r'\bwhat\b', r'\bwho\b', r'\bwhen\b', r'\bwhere\b', r'\bwhy\b', r'\bhow\b',
        r'\bcan\s+you\b', r'\bcould\s+you\b', r'\btell\s+me\b', r'\bexplain\b'
    ]

    BOT_ALIASES = ["ezic", "yeager", "ezicyeager", "butler"]

    @classmethod
    def is_addressed_by_name(cls, text: str) -> bool:
        """Checks if text mentions the bot by any of its recognizable names or aliases."""
        clean = text.lower()
        bot_name = settings.BOT_NAME.lower()
        aliases = set(cls.BOT_ALIASES)
        aliases.add(bot_name)
        for part in re.findall(r'[a-zA-Z0-9]+', bot_name):
            if len(part) >= 3:
                aliases.add(part)

        for alias in aliases:
            if re.search(rf'\b{re.escape(alias)}\b', clean):
                return True
        return False

    @classmethod
    def should_butler_respond(
        cls,
        text: str,
        is_reply_to_bot: bool = False,
        is_bot_mentioned: bool = False,
        is_private_chat: bool = False
    ) -> Tuple[bool, bool]:
        """
        Determines:
        1. should_respond (bool)
        2. requires_web_search (bool)
        """
        clean_text = text.strip().lower()
        if not clean_text:
            return False, False

        # In private 1-on-1 chat with the bot, always respond
        if is_private_chat:
            needs_search = cls.requires_web_search(clean_text)
            return True, needs_search

        # If user explicitly replied to the bot's message
        if is_reply_to_bot:
            needs_search = cls.requires_web_search(clean_text)
            return True, needs_search

        # If user tagged the bot username (@Bot)
        if is_bot_mentioned:
            needs_search = cls.requires_web_search(clean_text)
            return True, needs_search

        # If user addressed the bot by name (e.g. "oi ezic how are you", "yo butler", "hey yeager")
        if cls.is_addressed_by_name(clean_text):
            needs_search = cls.requires_web_search(clean_text)
            return True, needs_search

        # If user asked a clear question directed at the room/assistant that requires search
        if cls.requires_web_search(clean_text) and any(re.search(qw, clean_text) for qw in cls.QUESTION_WORDS):
            return True, True

        # Otherwise, don't interrupt human conversations!
        return False, False

    @classmethod
    def requires_web_search(cls, text: str) -> bool:
        """Checks if current/live external web search is appropriate."""
        lower = text.lower()
        return any(pattern.search(lower) for pattern in cls.NEWS_PATTERNS)


intent_classifier = IntentClassifier()
