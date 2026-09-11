from typing import List, Dict
from bot.database.models import TranslationGlossary


class GlossaryManager:
    """Manages custom terminology and translation overrides."""

    @staticmethod
    def format_glossary_prompt(entries: List[TranslationGlossary]) -> str:
        if not entries:
            return ""

        lines = ["\n[Mandatory Terminology Overrides]:"]
        for entry in entries:
            lines.append(f"- '{entry.source_text}' -> '{entry.target_text}'")
        lines.append("")
        return "\n".join(lines)


glossary_manager = GlossaryManager()
