"""
Translation package: detector, slang, glossary, quality, and translator engine.
"""
from bot.translation.detector import language_detector, LanguageDetector
from bot.translation.slang import slang_manager, SlangManager
from bot.translation.glossary import glossary_manager, GlossaryManager
from bot.translation.quality import quality_checker, QualityChecker
from bot.translation.translator import translator, get_translation_engine, TranslationEngine

__all__ = [
    "language_detector",
    "LanguageDetector",
    "slang_manager",
    "SlangManager",
    "glossary_manager",
    "GlossaryManager",
    "quality_checker",
    "QualityChecker",
    "translator",
    "get_translation_engine",
    "TranslationEngine",
]
