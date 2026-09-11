import hashlib
import time
from collections import OrderedDict
from typing import Optional, Any, Dict
from bot.config import settings
from bot.utils.logging import logger


class TTLCache:
    """Thread-safe, lightweight async-compatible LRU + TTL Cache."""
    def __init__(self, maxsize: int = 5000, default_ttl: int = 3600):
        self.maxsize = maxsize
        self.default_ttl = default_ttl
        self._data: OrderedDict[str, Any] = OrderedDict()
        self._expires: Dict[str, float] = {}

    def get(self, key: str) -> Optional[Any]:
        now = time.time()
        if key in self._data:
            if self._expires.get(key, 0) > now:
                self._data.move_to_end(key)
                return self._data[key]
            else:
                self.delete(key)
        return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        now = time.time()
        expire_at = now + (ttl if ttl is not None else self.default_ttl)

        if key in self._data:
            self._data.move_to_end(key)
        self._data[key] = value
        self._expires[key] = expire_at

        # Evict oldest if exceeding maxsize
        if len(self._data) > self.maxsize:
            oldest_key, _ = self._data.popitem(last=False)
            self._expires.pop(oldest_key, None)

    def delete(self, key: str) -> None:
        self._data.pop(key, None)
        self._expires.pop(key, None)

    def contains(self, key: str) -> bool:
        return self.get(key) is not None


class CacheManager:
    """Unified cache coordinator supporting in-memory LRU and optional Redis."""
    def __init__(self):
        # 1. Message Deduplication cache: tracks (chat_id, message_id) for 3 minutes
        self.dedup_cache = TTLCache(maxsize=10000, default_ttl=180)

        # 2. Translation cache: stores translations for 24h
        self.translation_cache = TTLCache(
            maxsize=10000,
            default_ttl=settings.TRANSLATION_CACHE_TTL_SECONDS
        )

        # 3. Group Config cache: caches group settings for 60 seconds to avoid DB pounding
        self.group_config_cache = TTLCache(maxsize=1000, default_ttl=60)

        # 4. User rate limiting cache: tracks user activity
        self.rate_limit_cache = TTLCache(maxsize=5000, default_ttl=5)

    @staticmethod
    def generate_translation_hash(text: str, target_lang: str) -> str:
        """Generates a SHA-256 hash for source text and target language."""
        normalized = text.strip().lower()
        key = f"{target_lang.lower()}:{normalized}"
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    def is_duplicate_message(self, chat_id: int, message_id: int) -> bool:
        """Checks if a message update was already received and processed."""
        key = f"{chat_id}:{message_id}"
        if self.dedup_cache.contains(key):
            return True
        self.dedup_cache.set(key, True)
        return False

    def get_cached_translation(self, text: str, target_lang: str) -> Optional[str]:
        h = self.generate_translation_hash(text, target_lang)
        return self.translation_cache.get(h)

    def set_cached_translation(self, text: str, target_lang: str, translated_text: str) -> None:
        h = self.generate_translation_hash(text, target_lang)
        self.translation_cache.set(h, translated_text)

    def get_cached_group(self, group_id: int) -> Optional[Any]:
        return self.group_config_cache.get(f"group:{group_id}")

    def set_cached_group(self, group_id: int, group_obj: Any) -> None:
        self.group_config_cache.set(f"group:{group_id}", group_obj)

    def invalidate_group(self, group_id: int) -> None:
        self.group_config_cache.delete(f"group:{group_id}")


cache_manager = CacheManager()
