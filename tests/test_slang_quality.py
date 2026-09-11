import unittest
from bot.translation.slang import slang_manager
from bot.translation.quality import quality_checker


class TestSlangAndQuality(unittest.TestCase):

    def test_slang_matching_persian(self):
        text = "این داداش ما واقعا ستون و اسکل هست"
        matches = slang_manager.find_matching_slang(text, language="fa")
        matched_sources = [m["source"] for m in matches]
        self.assertIn("داداش", matched_sources)
        self.assertIn("ستون", matched_sources)
        self.assertIn("اسکل", matched_sources)

    def test_slang_guidance_generation(self):
        text = "گه نخور عوضی"
        guidance = slang_manager.build_slang_guidance(text, language="fa")
        self.assertIn("گه نخور", guidance)
        self.assertIn("عوضی", guidance)

    def test_quality_cleaning(self):
        # AI preamble removal
        cleaned = quality_checker.clean_output("Here is the translation: Hello world")
        self.assertEqual(cleaned, "Hello world")

        # Quoted text cleanup
        cleaned_quotes = quality_checker.clean_output('"What is going on?"')
        self.assertEqual(cleaned_quotes, "What is going on?")

        # NO_TRANSLATION detection
        self.assertIsNone(quality_checker.clean_output("NO_TRANSLATION"))
        self.assertIsNone(quality_checker.clean_output("NO_TRANSLATION."))

    def test_valid_translation_validation(self):
        self.assertFalse(quality_checker.is_valid_translation("hello", "hello"))
        self.assertFalse(quality_checker.is_valid_translation("hello", ""))
        self.assertTrue(quality_checker.is_valid_translation("سلام", "Hello"))


if __name__ == "__main__":
    unittest.main()
