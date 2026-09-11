from typing import Set, List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Telegram Credentials
    TELEGRAM_BOT_TOKEN: str = "8834177471:AAH_RfDnZ_XV15qO05ZVBcM6HXZuBzikGGE"
    OWNER_IDS: Union[Set[int], List[int], str] = {5429173364}
    OWNER_USERNAMES: Union[Set[str], List[str], str] = {"merlin_hermis"}

    # Bot Identity & Defaults
    BOT_NAME: str = "EzicYeager"
    DEFAULT_TARGET_LANGUAGE: str = "en"
    DEFAULT_TRANSLATION_MODEL: str = "gemini-3.5-flash-lite"
    TRANSLATION_PROVIDER: str = "gemini"  # "gemini" or "openai"

    # AI API Keys
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

    # Web Search Configuration
    WEB_SEARCH_PROVIDER: str = "duckduckgo"  # "duckduckgo", "tavily", "serper"
    WEB_SEARCH_API_KEY: str = ""

    # Keep-Alive & Self-Pinging for Free Tier Hosts (Render, Koyeb, etc.)
    RENDER_EXTERNAL_URL: str = ""
    KEEP_ALIVE_URL: str = ""

    # Database & Cache
    DATABASE_URL: str = "sqlite+aiosqlite:///data/bot.db"
    REDIS_URL: str = ""

    # Memory & Caching
    MEMORY_MAX_MESSAGES: int = 15
    MEMORY_TTL_MINUTES: int = 60
    TRANSLATION_CACHE_TTL_SECONDS: int = 86400  # 24 hours

    # Logging & Observability
    LOG_LEVEL: str = "INFO"
    PORT: int = 8080

    @field_validator("OWNER_IDS", mode="before")
    @classmethod
    def parse_owner_ids(cls, v: Union[str, int, List, Set]) -> Set[int]:
        if isinstance(v, (int, float)):
            return {int(v)}
        if isinstance(v, (list, set)):
            return {int(x) for x in v if str(x).strip().isdigit()}
        if isinstance(v, str):
            ids = set()
            for part in v.replace(",", " ").replace(";", " ").split():
                clean = part.strip()
                if clean.isdigit():
                    ids.add(int(clean))
            return ids
        return set()

    @field_validator("OWNER_USERNAMES", mode="before")
    @classmethod
    def parse_owner_usernames(cls, v: Union[str, List, Set]) -> Set[str]:
        if isinstance(v, (list, set)):
            return {str(x).lower().lstrip("@").strip() for x in v if str(x).strip()}
        if isinstance(v, str):
            names = set()
            for part in v.replace(",", " ").replace(";", " ").split():
                clean = part.lower().lstrip("@").strip()
                if clean:
                    names.add(clean)
            return names
        return set()

    @property
    def is_gemini_available(self) -> bool:
        return bool(self.GEMINI_API_KEY and len(self.GEMINI_API_KEY.strip()) > 5)

    @property
    def is_openai_available(self) -> bool:
        return bool(self.OPENAI_API_KEY and len(self.OPENAI_API_KEY.strip()) > 5)


# Global settings singleton
settings = Settings()
