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
    def __init__(self, api_key: str, model_name: str = "gemini-3.5-flash-lite"):
        self.api_key = api_key
        self.primary_model = model_name or "gemini-3.5-flash-lite"
        self.fallback_models: List[str] = [
            self.primary_model,
            "gemini-flash-lite-latest",
            "gemini-3.5-flash-lite",
            "gemini-3.1-flash-lite",
            "gemini-3.7-flash",
            "gemini-3.6-flash"
        ]
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


class FreeTranslationEngine:
    """High-reliability emergency fallback engine using Google's public translation endpoint.
    Guarantees the bot NEVER stops translating even if Gemini/OpenAI run out of quota or keys expire.
    """
    async def translate(
        self,
        text: str,
        target_lang: str = "en",
        detected_lang: Optional[str] = None,
        preserve_profanity: bool = True
    ) -> Optional[str]:
        if not text.strip():
            return None

        cached = cache_manager.get_cached_translation(text, target_lang)
        if cached:
            return cached

        # First attempt: Google Chrome Extension endpoint (fast, zero auth, resilient)
        try:
            import aiohttp
            import urllib.parse
            url = (
                f"https://clients5.google.com/translate_a/t?client=dict-chrome-ex&sl=auto"
                f"&tl={urllib.parse.quote(target_lang)}&q={urllib.parse.quote(text)}"
            )
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            }
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json(content_type=None)
                        if data and isinstance(data, list) and len(data) > 0 and len(data[0]) > 0:
                            translated = data[0][0]
                            cleaned = quality_checker.clean_output(translated)
                            if cleaned and quality_checker.is_valid_translation(text, cleaned):
                                cache_manager.set_cached_translation(text, target_lang, cleaned)
                                logger.info(f"Fallback translation succeeded via Chrome-Ex: '{cleaned[:30]}...'")
                                return cleaned
        except Exception as ce:
            logger.warning(f"Chrome-Ex fallback translation error: {ce}")

        # Second attempt: MyMemory public API
        try:
            import aiohttp
            import urllib.parse
            src = detected_lang or "auto"
            langpair = f"{src}|{target_lang}"
            url = f"https://api.mymemory.translated.net/get?q={urllib.parse.quote(text)}&langpair={urllib.parse.quote(langpair)}"
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, headers={"User-Agent": "Mozilla/5.0"}) as resp:
                    if resp.status == 200:
                        data = await resp.json(content_type=None)
                        translated = data.get("responseData", {}).get("translatedText")
                        cleaned = quality_checker.clean_output(translated)
                        if cleaned and quality_checker.is_valid_translation(text, cleaned):
                            cache_manager.set_cached_translation(text, target_lang, cleaned)
                            logger.info(f"Fallback translation succeeded via MyMemory: '{cleaned[:30]}...'")
                            return cleaned
        except Exception as me:
            logger.warning(f"MyMemory fallback translation error: {me}")

        return None


class ResilientTranslationEngine:
    """Orchestrates multi-tiered translation:
    1. Primary LLM Engine (Gemini with multi-model failover, or OpenAI)
    2. Secondary LLM Engine (OpenAI if available, or Gemini)
    3. Emergency Free Engine (Chrome-Ex / MyMemory)
    """
    def __init__(self):
        self.gemini_engine = None
        self.openai_engine = None
        self.free_engine = FreeTranslationEngine()

        if settings.is_gemini_available:
            self.gemini_engine = GeminiTranslationEngine(
                api_key=settings.GEMINI_API_KEY,
                model_name=settings.DEFAULT_TRANSLATION_MODEL
            )

        if settings.is_openai_available:
            self.openai_engine = OpenAITranslationEngine(
                api_key=settings.OPENAI_API_KEY
            )

    async def translate(
        self,
        text: str,
        target_lang: str = "en",
        detected_lang: Optional[str] = None,
        preserve_profanity: bool = True
    ) -> Optional[str]:
        # 1. Primary Engine
        if settings.TRANSLATION_PROVIDER.lower() == "openai" and self.openai_engine:
            res = await self.openai_engine.translate(text, target_lang, detected_lang, preserve_profanity)
            if res:
                return res
        elif self.gemini_engine:
            res = await self.gemini_engine.translate(text, target_lang, detected_lang, preserve_profanity)
            if res:
                return res

        # 2. Secondary Engine (Try the other LLM if configured)
        if self.openai_engine and settings.TRANSLATION_PROVIDER.lower() != "openai":
            res = await self.openai_engine.translate(text, target_lang, detected_lang, preserve_profanity)
            if res:
                return res
        elif self.gemini_engine and settings.TRANSLATION_PROVIDER.lower() == "openai":
            res = await self.gemini_engine.translate(text, target_lang, detected_lang, preserve_profanity)
            if res:
                return res

        # 3. Emergency Free Fallback (Never leaves messages untranslated!)
        return await self.free_engine.translate(text, target_lang, detected_lang, preserve_profanity)


def get_translation_engine() -> TranslationEngine:
    """Factory returning the resilient translation engine."""
    return ResilientTranslationEngine()


translator = get_translation_engine()
