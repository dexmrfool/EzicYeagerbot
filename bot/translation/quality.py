import re
from typing import Optional


class QualityChecker:
    """Post-translation sanitization, validation, and formatting."""

    AI_PREAMBLE_PATTERNS = [
        re.compile(r'^(?:here(?:\s+is|\'s)\s+the\s+translation(?:\s*:\s*)?)', re.IGNORECASE),
        re.compile(r'^(?:translation\s*:\s*)', re.IGNORECASE),
        re.compile(r'^(?:translated(?:\s+text)?\s*:\s*)', re.IGNORECASE),
        re.compile(r'^(?:in\s+english\s*:\s*)', re.IGNORECASE),
    ]

    @classmethod
    def clean_output(cls, text: Optional[str]) -> Optional[str]:
        if not text:
            return None

        clean = text.strip()

        # If model explicitly determined no translation was required
        if "NO_TRANSLATION" in clean or clean == "NO_TRANSLATION.":
            return None

        # Strip enclosing quotes if model added them
        if (clean.startswith('"') and clean.endswith('"')) or (clean.startswith("'") and clean.endswith("'")):
            clean = clean[1:-1].strip()

        # Strip preamble lines
        for pattern in cls.AI_PREAMBLE_PATTERNS:
            clean = pattern.sub('', clean).strip()

        if not clean:
            return None

        return clean

    @classmethod
    def is_valid_translation(cls, original_text: str, translated_text: Optional[str]) -> bool:
        if not translated_text:
            return False

        orig_clean = original_text.strip().lower()
        trans_clean = translated_text.strip().lower()

        # If translation is identical to original, no meaningful translation occurred
        if orig_clean == trans_clean:
            return False

        return True


quality_checker = QualityChecker()
