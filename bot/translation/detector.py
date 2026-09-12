import re
from typing import Optional, Tuple
from bot.utils.text import detect_script_heuristic, detect_romanized_heuristic


class LanguageDetector:
    """
    Two-stage language detection engine.
    Stage 1: Fast local Unicode script analysis and Romanization markers (0ms latency).
    Stage 2: Model fallback for mixed or ambiguous language text.
    """

    SCRIPT_TO_LANG = {
        "persian_arabic": "fa",
        "burmese": "my",
        "devanagari": "hi",
        "japanese": "ja",
        "cyrillic": "ru",
        "thai": "th"
    }

    COMMON_ENGLISH_WORDS = {
        # Pronouns, articles, prepositions, conjunctions
        "the", "be", "to", "of", "and", "a", "in", "that", "have", "i", "it",
        "for", "not", "on", "with", "he", "as", "you", "do", "at", "this",
        "but", "his", "by", "from", "they", "we", "say", "her", "she", "or",
        "an", "will", "my", "one", "all", "would", "there", "their", "what",
        "so", "up", "out", "if", "about", "who", "get", "which", "go", "me",
        "when", "make", "can", "like", "time", "no", "just", "him", "know",
        "take", "people", "into", "year", "your", "good", "some", "could",
        "them", "see", "other", "than", "then", "now", "look", "only", "come",
        "its", "over", "think", "also", "back", "after", "use", "two", "how",
        "our", "work", "first", "well", "way", "even", "new", "want", "because",
        "any", "these", "give", "day", "most", "us",

        # Common conversational forms & verbs
        "is", "am", "are", "was", "were", "been", "being",
        "has", "had", "having", "does", "did", "done", "doing",
        "hey", "hello", "today", "tomorrow", "yesterday", "tonight",
        "everything", "everyone", "someone", "nothing", "anything", "something",
        "bro", "dude", "guy", "guys", "man", "mate", "friend", "friends",
        "yes", "yeah", "yep", "nah", "ok", "okay", "sure", "fine", "alright",
        "lol", "lmao", "fr", "ngl", "tbh", "gg", "w", "l", "great", "awesome",
        "nice", "cool", "fire", "bad", "worst", "better", "best", "love", "hate",
        "watch", "watching", "watched", "play", "playing", "played", "game",
        "anime", "manga", "episode", "chapter", "season", "movie", "series",
        "one", "piece", "bleach", "naruto", "dragon", "ball", "jujutsu", "kaisen",
        "please", "thanks", "thank", "welcome", "sorry", "wait", "ready",
        "talk", "talking", "tell", "telling", "ask", "asking", "answer",
        "help", "need", "feel", "feeling", "look", "looking", "find", "found",
        "happy", "sad", "tired", "busy", "home", "work", "life", "shit", "fuck",
        "damn", "bitch", "ass", "dick", "crap", "bullshit", "crazy", "weird",

        # Common internet slang, greetings, acronyms & single-word tokens
        "yo", "hi", "hey", "sup", "gm", "gn", "bye", "cya", "np", "ty", "thx",
        "pls", "plz", "idk", "idc", "wdym", "omg", "wtf", "bruh", "bruv", "kk",
        "oof", "yea", "yeah", "yup", "aight", "rn", "fr", "ngl", "tbh", "smh",
        "afaik", "imo", "gtg", "brb", "hru", "wbu", "nah", "nope", "ez", "cct",
        "give", "me", "done", "got", "can", "could", "gotta", "gonna", "wanna"
    }

    @classmethod
    def is_likely_pure_english(cls, text: str) -> bool:
        """Determines if the text is clearly English without foreign scripts or romanization."""
        # 1. Non-latin script check
        script, ratio = detect_script_heuristic(text)
        if script and script != "latin" and ratio > 0.15:
            return False

        # 2. Romanized foreign language check
        if detect_romanized_heuristic(text):
            return False

        # 3. Extract alpha words
        words = re.findall(r'\b[a-zA-Z]{2,}\b', text.lower())
        if not words:
            return True  # Pure numbers, emojis, or punctuation

        matches = 0
        for w in words:
            if w in cls.COMMON_ENGLISH_WORDS:
                matches += 1
            elif (w.endswith("ing") and len(w) > 4) or \
                 (w.endswith("ed") and len(w) > 3) or \
                 (w.endswith("ly") and len(w) > 3) or \
                 (w.endswith("s") and len(w) > 3 and w[:-1] in cls.COMMON_ENGLISH_WORDS):
                matches += 1

        match_ratio = matches / len(words)
        return match_ratio >= 0.70

    @classmethod
    def should_translate(cls, text: str, target_lang: str = "en") -> Tuple[bool, Optional[str]]:
        """
        Evaluates whether an incoming message needs translation into the target language.
        Returns (needs_translation, detected_lang_hint).
        """
        clean_text = text.strip()
        if not clean_text or len(clean_text) <= 1:
            return False, None

        # Ignore pure URLs, numbers, or command-like tokens
        if re.match(r'^https?://\S+$', clean_text) or clean_text.isdigit():
            return False, None

        # 1. Unicode script detection (non-Latin scripts: Persian, Burmese, Devanagari, Japanese, etc.)
        script, ratio = detect_script_heuristic(clean_text)
        if script and script != "latin" and ratio >= 0.15:
            lang_code = cls.SCRIPT_TO_LANG.get(script, "unknown")
            if lang_code == target_lang.lower():
                return False, lang_code
            return True, lang_code

        # 2. Check Romanized foreign text (e.g. Hinglish, Fingilish in Latin alphabet)
        romanized = detect_romanized_heuristic(clean_text)
        if romanized:
            lang_code = "hi" if "hi" in romanized else "fa"
            if lang_code != target_lang.lower():
                return True, lang_code

        # 3. If target is English: evaluate if pure English
        if target_lang.lower() in ("en", "english"):
            if cls.is_likely_pure_english(clean_text):
                return False, "en"

            # If Latin script with NO foreign markers:
            # Short messages (<= 4 words) are almost certainly English slang, nicknames, or abbreviations
            words = re.findall(r'\b[a-zA-Z]+\b', clean_text.lower())
            if len(words) <= 4:
                return False, "en"

            # Ambiguous longer Latin script text
            return True, "unknown"

        # If target language is non-English (e.g. Persian/Burmese), translate English messages
        return True, "en"


language_detector = LanguageDetector()
