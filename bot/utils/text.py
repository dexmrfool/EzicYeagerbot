import re
import unicodedata
from typing import Optional, Tuple, Dict


# Unicode script ranges
UNICODE_RANGES = {
    "persian_arabic": (
        (0x0600, 0x06FF),  # Arabic
        (0x0750, 0x077F),  # Arabic Supplement
        (0xFB50, 0xFDFF),  # Arabic Presentation Forms-A
        (0xFE70, 0xFEFF),  # Arabic Presentation Forms-B
    ),
    "burmese": (
        (0x1000, 0x109F),  # Myanmar
        (0xAA60, 0xAA7F),  # Myanmar Extended-A
        (0xA9E0, 0xA9FF),  # Myanmar Extended-B
    ),
    "devanagari": (
        (0x0900, 0x097F),  # Devanagari (Hindi, Marathi, Sanskrit)
        (0xA8E0, 0xA8FF),  # Devanagari Extended
    ),
    "japanese": (
        (0x3040, 0x309F),  # Hiragana
        (0x30A0, 0x30FF),  # Katakana
        (0x4E00, 0x9FFF),  # CJK Unified Ideographs
    ),
    "cyrillic": (
        (0x0400, 0x04FF),  # Cyrillic (Russian, Ukrainian)
    ),
    "thai": (
        (0x0E00, 0x0E7F),  # Thai
    ),
}

# Common Romanized words indicative of Romanized languages (Hinglish, Fingilish, etc.)
ROMANIZED_MARKERS = {
    "hi_romanized": {
        "bhai", "yaar", "kya", "hai", "nahi", "hoga", "karo", "kaise", "achha",
        "theek", "batao", "chal", "raha", "meri", "mera", "tere", "tera", "apna",
        "bahut", "kuch", "sahi", "gaya", "gayi", "chutiya", "bhenchod", "gandu",
        "wakt", "waqt", "wakth", "lega", "legi", "lenge", "toda", "thoda", "thodi",
        "kise", "yara", "krta", "karta", "esi", "aisi", "dikti", "dikhta", "dikhti",
        "pass", "bass", "bas", "bath", "baat", "bata", "bol", "bolo", "de", "do",
        "diya", "le", "lo", "liya", "syd", "shyd", "shayad", "sab", "kab", "kaha",
        "kyun", "kyu", "mat", "dekh", "dekho", "dekha", "karega", "karegi", "karenge",
        "bolte", "bolti", "krte", "krti", "samjha", "samjhe", "pata", "pta", "chalega"
    },
    "fa_romanized": {
        "chetori", "khobi", "dadash", "salam", "khoobam", "merc", "merci",
        "mamnoon", "ghorbanat", "fadat", "chakeram", "nokaram", "damet", "garm",
        "are", "na", "bale", "chera", "koja", "chi", "inam", "haji"
    }
}


def analyze_text_scripts(text: str) -> Dict[str, float]:
    """
    Computes the percentage of characters in text that belong to known Unicode scripts.
    Excludes punctuation, emojis, and whitespace.
    """
    if not text:
        return {}

    total_alpha = 0
    counts: Dict[str, int] = {k: 0 for k in UNICODE_RANGES}
    counts["latin"] = 0

    for ch in text:
        if ch.isspace() or unicodedata.category(ch).startswith(('P', 'S', 'C')):
            continue

        code = ord(ch)
        total_alpha += 1
        matched = False

        for script_name, ranges in UNICODE_RANGES.items():
            if any(start <= code <= end for start, end in ranges):
                counts[script_name] += 1
                matched = True
                break

        if not matched and ('A' <= ch <= 'Z' or 'a' <= ch <= 'z'):
            counts["latin"] += 1

    if total_alpha == 0:
        return {}

    return {k: v / total_alpha for k, v in counts.items() if v > 0}


def detect_script_heuristic(text: str) -> Tuple[Optional[str], float]:
    """
    Fast stage-1 script heuristic.
    Returns (dominant_script, confidence_ratio).
    """
    scripts = analyze_text_scripts(text)
    if not scripts:
        return None, 0.0

    dominant = max(scripts.items(), key=lambda x: x[1])
    return dominant[0], dominant[1]


def detect_romanized_heuristic(text: str) -> Optional[str]:
    """
    Detects if Latin-script text contains prominent Romanized words (Hinglish, Fingilish).
    """
    words = set(re.findall(r'\b[a-zA-Z]{2,}\b', text.lower()))
    if not words:
        return None

    for lang, markers in ROMANIZED_MARKERS.items():
        overlap = words.intersection(markers)
        if len(overlap) >= 2 or (len(words) <= 3 and len(overlap) >= 1):
            return lang

    return None


def clean_text_for_comparison(text: str) -> str:
    """Normalizes whitespace and lowercases text for deduplication caching."""
    return re.sub(r'\s+', ' ', text).strip().lower()


def format_translation_reply(translated_text: str, source_lang: Optional[str] = None, target_lang: str = "en") -> str:
    """
    Formats the translation output for Telegram.
    Clean, non-intrusive, clear to group members.
    """
    # E.g. "🌐 [Translation]\n{translated_text}"
    return f"🌐 {translated_text}"
