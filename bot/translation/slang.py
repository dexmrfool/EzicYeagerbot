import json
import os
from typing import Dict, List, Optional


class SlangManager:
    """
    Manages language-specific slang, profanity, and idiom dictionaries.
    Provides prompt context for LLM translation to ensure uninhibited, accurate preservation.
    """
    def __init__(self):
        self._dictionaries: Dict[str, List[Dict[str, str]]] = {}
        self.load_local_glossaries()

    def load_local_glossaries(self) -> None:
        """Loads default JSON glossaries from the data directory."""
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        data_dir = os.path.join(base_dir, "data")

        if not os.path.exists(data_dir):
            return

        for fname in os.listdir(data_dir):
            if fname.startswith("glossary_") and fname.endswith(".json"):
                fpath = os.path.join(data_dir, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        lang = data.get("language", "general")
                        self._dictionaries[lang] = data.get("entries", [])
                except Exception:
                    pass

    def find_matching_slang(self, text: str, language: Optional[str] = None) -> List[Dict[str, str]]:
        """Identifies any specific slang/profanity terms contained in text."""
        lower_text = text.lower()
        matches = []

        langs_to_check = [language] if language and language in self._dictionaries else list(self._dictionaries.keys())

        for lang in langs_to_check:
            entries = self._dictionaries.get(lang, [])
            for entry in entries:
                src = entry.get("source", "").lower()
                if src and (src in lower_text or f" {src} " in f" {lower_text} "):
                    matches.append(entry)

        return matches

    def build_slang_guidance(self, text: str, language: Optional[str] = None) -> str:
        """Constructs model guidance block for identified slang in the message."""
        matched = self.find_matching_slang(text, language)
        if not matched:
            return ""

        guidance_lines = ["\n[Contextual Slang & Profanity Translations]:"]
        for m in matched[:8]:  # Limit top 8 matches to avoid prompt bloat
            guidance_lines.append(f"- '{m['source']}': translates naturally to '{m['target']}' ({m.get('category', 'slang')})")

        guidance_lines.append("Use these natural equivalents while matching the speaker's emotional tone and intensity.\n")
        return "\n".join(guidance_lines)


slang_manager = SlangManager()
