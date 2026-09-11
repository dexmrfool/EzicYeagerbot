import unittest
from bot.translation.detector import language_detector
from bot.utils.text import detect_script_heuristic, detect_romanized_heuristic


class TestLanguageDetector(unittest.TestCase):

    def test_persian_detection(self):
        text = "سلام داداش چطوری خوبی؟"
        script, ratio = detect_script_heuristic(text)
        self.assertEqual(script, "persian_arabic")
        self.assertGreater(ratio, 0.8)

        should_trans, lang_hint = language_detector.should_translate(text, target_lang="en")
        self.assertTrue(should_trans)
        self.assertEqual(lang_hint, "fa")

    def test_burmese_detection(self):
        text = "မင်္ဂလာပါ ဘရို နေကောင်းလား"
        script, ratio = detect_script_heuristic(text)
        self.assertEqual(script, "burmese")
        self.assertGreater(ratio, 0.8)

        should_trans, lang_hint = language_detector.should_translate(text, target_lang="en")
        self.assertTrue(should_trans)
        self.assertEqual(lang_hint, "my")

    def test_devanagari_detection(self):
        text = "नमस्ते भाई क्या हाल चाल है?"
        script, ratio = detect_script_heuristic(text)
        self.assertEqual(script, "devanagari")
        self.assertGreater(ratio, 0.8)

        should_trans, lang_hint = language_detector.should_translate(text, target_lang="en")
        self.assertTrue(should_trans)
        self.assertEqual(lang_hint, "hi")

    def test_romanized_hinglish(self):
        text = "bhai kya chal raha hai aaj"
        romanized = detect_romanized_heuristic(text)
        self.assertEqual(romanized, "hi_romanized")

        should_trans, lang_hint = language_detector.should_translate(text, target_lang="en")
        self.assertTrue(should_trans)
        self.assertEqual(lang_hint, "hi")

    def test_pure_english_skipped(self):
        text = "hey bro how are you doing today? is everything good?"
        should_trans, lang_hint = language_detector.should_translate(text, target_lang="en")
        self.assertFalse(should_trans)
        self.assertEqual(lang_hint, "en")

    def test_empty_and_urls_skipped(self):
        self.assertFalse(language_detector.should_translate("")[0])
        self.assertFalse(language_detector.should_translate("https://t.me/example")[0])
        self.assertFalse(language_detector.should_translate("123456")[0])


if __name__ == "__main__":
    unittest.main()
