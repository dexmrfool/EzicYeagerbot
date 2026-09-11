import asyncio
from typing import Optional, Protocol, List
from bot.config import settings
from bot.cache.manager import cache_manager
from bot.translation.slang import slang_manager
from bot.translation.quality import quality_checker
from bot.utils.logging import logger


class TranslationEngine(Protocol):
    async def translate(
        self,
        text: str,
        target_lang: str = "en",
        detected_lang: Optional[str] = None,
        preserve_profanity: bool = True
    ) -> Optional[str]:
        ...


class GeminiTranslationEngine:
    """Production translation engine utilizing Google Gemini models with automatic model fallback."""
    def __init__(self, api_key: str, model_name: str = "gemini-3.6-flash"):
        self.api_key = api_key
        self.primary_model = model_name
        self.fallback_models: List[str] = [model_name or "gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite"]
        # Deduplicate while preserving order
        self.candidate_models = list(dict.fromkeys(self.fallback_models))
        self.client = None
        self._init_client()

    def _init_client(self):
        try:
            from google import genai
            self.client = genai.Client(api_key=self.api_key)
        except Exception as e:
            logger.error(f"Failed to initialize Google GenAI Client: {e}")

    async def translate(
        self,
        text: str,
        target_lang: str = "en",
        detected_lang: Optional[str] = None,
        preserve_profanity: bool = True
    ) -> Optional[str]:
        if not self.client or not text.strip():
            return None

        # 1. Check in-memory / DB cache
        cached = cache_manager.get_cached_translation(text, target_lang)
        if cached:
            return cached

        # 2. Extract contextual slang/profanity guidance
        slang_guidance = slang_manager.build_slang_guidance(text, detected_lang)

        # 3. Formulate strict prompt
        prompt = (
            f"You are a master multilingual translator for an active Telegram group.\n"
            f"Your task is to translate the input message into target language: '{target_lang}'.\n\n"
            f"RULES:\n"
            f"1. If the message is already predominantly in the target language ('{target_lang}') or contains no meaningful foreign words requiring translation, output EXACTLY 'NO_TRANSLATION'.\n"
            f"2. CRITICAL - UNFILTERED PROFANITY & SLANG PRESERVATION: If the message contains profanity, vulgarity, insults, sexual terms, or street slang, do NOT censor, soften, sanitize, or star out letters. Translate them into the closest natural, authentic equivalent with matching intensity and bite.\n"
            f"3. Preserve emojis, exclamation marks, internet acronyms, capitalization, and emotional tone.\n"
            f"4. Understand mixed-language phrases (e.g. Burmese+English, Hinglish, Fingilish, Romanized text).\n"
            f"5. Output ONLY the translated message. No introductions, no notes, no quotes.\n"
            f"{slang_guidance}\n"
            f"Message to translate:\n"
            f"\"\"\"{text}\"\"\""
        )

        # 4. Generate translation with model fallback (fails over to next candidate immediately on 429/404)
        for model in self.candidate_models:
            try:
                response = await self.client.aio.models.generate_content(
                    model=model,
                    contents=prompt
                )
                raw_result = response.text if response else None
                cleaned = quality_checker.clean_output(raw_result)

                if cleaned and quality_checker.is_valid_translation(text, cleaned):
                    # Cache translation
                    cache_manager.set_cached_translation(text, target_lang, cleaned)
                    return cleaned
                elif cleaned is None and raw_result and "NO_TRANSLATION" in raw_result:
                    # Model explicitly indicated NO_TRANSLATION
                    return None

            except Exception as e:
                err_str = str(e)
                if "404" in err_str or "NOT_FOUND" in err_str:
                    logger.warning(f"Model {model} unavailable. Trying next fallback model...")
                    continue
                elif "429" in err_str or "quota" in err_str.lower():
                    logger.warning(f"Gemini rate limit on {model}. Failing over to next model...")
                    continue
                else:
                    logger.error(f"Gemini translation error on {model}: {e}")
                    continue

        return None


class OpenAITranslationEngine:
    """Production translation engine utilizing OpenAI / Groq compatible models."""
    def __init__(self, api_key: str, model_name: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.model_name = model_name
        self.client = None
        self._init_client()

    def _init_client(self):
        try:
            from openai import AsyncOpenAI
            self.client = AsyncOpenAI(api_key=self.api_key)
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI Client: {e}")

    async def translate(
        self,
        text: str,
        target_lang: str = "en",
        detected_lang: Optional[str] = None,
        preserve_profanity: bool = True
    ) -> Optional[str]:
        if not self.client or not text.strip():
            return None

        cached = cache_manager.get_cached_translation(text, target_lang)
        if cached:
            return cached

        slang_guidance = slang_manager.build_slang_guidance(text, detected_lang)

        system_prompt = (
            f"You are a master multilingual translator for a Telegram group. "
            f"Translate messages into '{target_lang}'. "
            f"If already in '{target_lang}', respond ONLY with 'NO_TRANSLATION'. "
            f"Never sanitize or censor vulgarity, profanity, or insults; preserve exact intensity and slang naturally. "
            f"Output ONLY the translated text."
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"{slang_guidance}\nTranslate: {text}"}
                ],
                temperature=0.2
            )
            raw = response.choices[0].message.content
            cleaned = quality_checker.clean_output(raw)
            if cleaned and quality_checker.is_valid_translation(text, cleaned):
                cache_manager.set_cached_translation(text, target_lang, cleaned)
                return cleaned
        except Exception as e:
            logger.error(f"OpenAI translation error: {e}")

        return None


def get_translation_engine() -> TranslationEngine:
    """Factory returning the configured translation engine."""
    provider = settings.TRANSLATION_PROVIDER.lower()
    if provider == "openai" and settings.is_openai_available:
        return OpenAITranslationEngine(api_key=settings.OPENAI_API_KEY)
    elif settings.is_gemini_available:
        return GeminiTranslationEngine(
            api_key=settings.GEMINI_API_KEY,
            model_name=settings.DEFAULT_TRANSLATION_MODEL
        )
    else:
        return GeminiTranslationEngine(
            api_key=settings.GEMINI_API_KEY or "DUMMY_KEY",
            model_name=settings.DEFAULT_TRANSLATION_MODEL
        )


translator = get_translation_engine()
