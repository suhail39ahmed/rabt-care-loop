"""Languages Rabt serves (Abu Dhabi population): English, Arabic, Hindi, Urdu, Malayalam, Filipino, Bengali.

The approved knowledge base and clinician-reviewed templates exist in English and Arabic. Other languages get
the English answer translated through the guarded translation layer (PII kept local, labelled AI-translated);
safety-critical texts (crisis, refusals, hand-offs) are fixed, reviewed strings in every language.
"""

from __future__ import annotations

import re

SUPPORTED: dict[str, str] = {
    "en": "English",
    "ar": "Arabic",
    "hi": "Hindi",
    "ur": "Urdu",
    "ml": "Malayalam",
    "tl": "Filipino (Tagalog)",
    "bn": "Bengali",
}
RTL = frozenset({"ar", "ur"})
KB_LANGS = frozenset({"en", "ar"})
LATIN = frozenset({"en", "tl"})

_SCRIPTS = {
    "hi": re.compile(r"[\u0900-\u097F]"),
    "bn": re.compile(r"[\u0980-\u09FF]"),
    "ml": re.compile(r"[\u0D00-\u0D7F]"),
    "arabic": re.compile(r"[\u0600-\u06FF\u0750-\u077F]"),
}
# Letters used in Urdu but not in standard Arabic.
_URDU = re.compile(r"[\u0679\u0688\u0691\u06BA\u06BE\u06C1\u06D2\u067E\u0686\u06AF\u06A9]")


def normalize(lang: str | None, default: str = "en") -> str:
    lang = (lang or "").lower()[:2]
    return lang if lang in SUPPORTED else default


def detect(text: str) -> str | None:
    """Language implied by the script, or None for Latin / no letters (English or Filipino)."""
    letters = [ch for ch in text or "" if ch.isalpha()]
    if not letters:
        return None
    for lang in ("hi", "bn", "ml"):
        if sum(1 for ch in letters if _SCRIPTS[lang].match(ch)) / len(letters) >= 0.5:
            return lang
    if sum(1 for ch in letters if _SCRIPTS["arabic"].match(ch)) / len(letters) >= 0.5:
        return "ur" if _URDU.search(text) else "ar"
    return None


def script_ok(text: str, lang: str) -> bool:
    """Does `text` look written in `lang`'s script? (Latin languages: mostly non-Arabic, non-Indic.)"""
    if lang in LATIN:
        return detect(text) is None
    found = detect(text)
    if lang in ("ar", "ur"):
        return found in ("ar", "ur")
    return found == lang


def kb_language(lang: str) -> str:
    return lang if lang in KB_LANGS else "en"
