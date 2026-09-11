from typing import Optional, List, Dict
from bot.config import settings
from bot.database.repository import BotRepository
from bot.butler.personality import personality_manager
from bot.butler.memory import memory_manager
from bot.web.search import search_engine
from bot.web.sources import source_formatter
from bot.utils.logging import logger


class ButlerBrain:
    """Central Butler AI orchestrator: intent evaluation, memory retrieval, search, and synthesis."""

    def __init__(self):
        self.gemini_client = None
        self._init_client()

    def _init_client(self):
        if settings.is_gemini_available:
            try:
                from google import genai
                self.gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
            except Exception as e:
                logger.error(f"Failed to initialize Gemini in Butler Brain: {e}")

    async def generate_response(
        self,
        repo: BotRepository,
        group_id: int,
        user_id: int,
        user_name: str,
        user_message: str,
        requires_web_search: bool = False,
        group_target_lang: str = "en"
    ) -> Optional[str]:
        system_prompt = personality_manager.get_system_prompt(group_target_lang)

        # 1. Fetch short-term conversation context
        history = await memory_manager.get_context_history(repo, group_id, limit=6)

        # 2. Perform live web search if needed
        search_context = ""
        if requires_web_search:
            try:
                logger.info(f"Butler conducting web search for query: '{user_message}'")
                search_results = await search_engine.search(user_message, max_results=3)
                search_context = source_formatter.format_for_prompt(search_results)
            except Exception as se:
                logger.error(f"Search failed in Butler Brain: {se}")

        # 3. Assemble prompt
        conversation_block = []
        for turn in history:
            role_label = "User" if turn["role"] == "user" else settings.BOT_NAME
            conversation_block.append(f"{role_label}: {turn['content']}")

        full_prompt = (
            f"{system_prompt}\n\n"
            f"{search_context}\n\n"
            f"[Recent Group Context]:\n" +
            ("\n".join(conversation_block) if conversation_block else "No prior history.") +
            f"\n\nUser ({user_name}): {user_message}\n"
            f"{settings.BOT_NAME}:"
        )

        # 4. Invoke LLM
        response_text = None
        if self.gemini_client:
            candidate_models = [
                settings.DEFAULT_TRANSLATION_MODEL or "gemini-3.6-flash",
                "gemini-3.5-flash",
                "gemini-3.5-flash-lite"
            ]
            for model in candidate_models:
                try:
                    response = await self.gemini_client.aio.models.generate_content(
                        model=model,
                        contents=full_prompt
                    )
                    if response and response.text:
                        response_text = response.text.strip()
                        break
                except Exception as ge:
                    logger.warning(f"Butler Gemini generation failed on {model} ({ge}). Trying next...")

        # OpenAI fallback if configured
        if not response_text and settings.is_openai_available:
            try:
                from openai import AsyncOpenAI
                oa_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
                oa_resp = await oa_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt + ("\n" + search_context if search_context else "")},
                        {"role": "user", "content": f"User ({user_name}): {user_message}"}
                    ],
                    max_tokens=350,
                    temperature=0.7
                )
                response_text = oa_resp.choices[0].message.content.strip()
            except Exception as oe:
                logger.error(f"Butler OpenAI generation error: {oe}")

        # 5. Record memory turn if successful
        if response_text:
            await memory_manager.record_turn(repo, group_id, user_id, "user", user_message)
            await memory_manager.record_turn(repo, group_id, 0, "assistant", response_text)

        return response_text


butler_brain = ButlerBrain()
