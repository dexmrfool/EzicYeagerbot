import unittest
from bot.config import settings
from bot.translation.translator import get_translation_engine
from bot.web.search import search_engine


class TestLiveEngines(unittest.IsolatedAsyncioTestCase):

    async def test_live_web_search(self):
        """Tests DuckDuckGo async search retrieval."""
        results = await search_engine.search("One Piece manga latest chapter", max_results=2)
        self.assertIsInstance(results, list)
        if results:
            self.assertIn("title", results[0])
            self.assertIn("snippet", results[0])

    async def test_live_translation_if_key_available(self):
        """Tests live Gemini translation with slang and profanity preservation."""
        if not settings.is_gemini_available:
            self.skipTest("GEMINI_API_KEY not configured for live test")

        engine = get_translation_engine()
        # Persian test message with street slang & insult
        persian_text = "داداش دهنت سرویس خیلی باحال بود"
        translated = await engine.translate(persian_text, target_lang="en", detected_lang="fa")

        self.assertIsNotNone(translated)
        self.assertIsInstance(translated, str)
        self.assertTrue(len(translated) > 2)
        # Should NOT contain censorship asterisks like f*** or d***
        self.assertNotIn("***", translated)


if __name__ == "__main__":
    unittest.main()
