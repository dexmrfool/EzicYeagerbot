from bot.config import settings
from bot.butler.prompts import get_butler_system_prompt


class PersonalityManager:
    """Manages the persona and conversational tone of Butler AI."""

    @staticmethod
    def get_system_prompt(group_target_lang: str = "en") -> str:
        return get_butler_system_prompt(group_target_lang)

    @staticmethod
    def get_bot_name() -> str:
        return settings.BOT_NAME


personality_manager = PersonalityManager()
