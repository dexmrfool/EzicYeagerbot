from typing import List, Dict
from bot.database.repository import BotRepository
from bot.config import settings


class ConversationMemoryManager:
    """Manages short-term conversation context scoped by group and user."""

    @staticmethod
    async def get_context_history(repo: BotRepository, group_id: int, limit: int = 10) -> List[Dict[str, str]]:
        """Fetches recent conversation turns formatted for LLM."""
        records = await repo.get_recent_memory(group_id, limit=limit)
        return [{"role": r.role, "content": r.content} for r in records]

    @staticmethod
    async def record_turn(repo: BotRepository, group_id: int, user_id: int, role: str, content: str) -> None:
        """Stores a message turn in conversation memory."""
        await repo.add_memory(group_id, user_id, role, content)


memory_manager = ConversationMemoryManager()
