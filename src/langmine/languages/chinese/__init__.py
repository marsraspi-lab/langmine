"""Chinese language extension for LangMine.

Provides:
  - ChineseLanguageService (LanguageProcessor implementation)
  - CcCedictAdapter (Dictionary implementation)
  - SubtlexChAdapter (FrequencySource implementation)
  - JiebaFrequencyAdapter (fallback FrequencySource)
  - get_hsk_level (HSK proficiency utility)
  - get_anki_templates() (Anki card templates from files)

Self-registers with the language factory at import time via
register_language() — no factory edits needed when adding a language.
"""

from pathlib import Path

from langmine.language_factory import register_language
from langmine.languages.chinese.dictionary import CcCedictAdapter
from langmine.languages.chinese.frequency import SubtlexChAdapter
from langmine.languages.chinese.hsk_data import get_hsk_level
from langmine.languages.chinese.jieba_frequency import JiebaFrequencyAdapter
from langmine.languages.chinese.service import ChineseLanguageService

# Language manifest — per-language metadata for Anki and UI
MANIFEST = {
    "name": "中文",
    "deck_name": "Chinese::Sentence Mining",
    "note_type": "LangMine Sentence",
    "cloze_note_type": "LangMine Cloze",
}

# YouTube transcript language codes to try, in preference order.
# youtube-transcript-api will try each until it finds a transcript
# (including auto-generated). The first match wins.
TRANSCRIPT_LANGUAGES = ["zh-Hans", "zh-Hant", "zh-CN", "zh-TW", "zh"]

# Standardized proficiency lookup (HSK 2.0)
get_proficiency_level = get_hsk_level

# Language-specific settings schema — rendered dynamically in the Settings UI
CHINESE_SETTINGS_SCHEMA = [
    {
        "key": "bootstrap_level",
        "label": "HSK Bootstrap Level",
        "type": "select",
        "default": 0,
        "options": [
            {"value": 0, "label": "Off"},
            {"value": 1, "label": "HSK 1"},
            {"value": 2, "label": "HSK 2"},
            {"value": 3, "label": "HSK 3"},
            {"value": 4, "label": "HSK 4"},
            {"value": 5, "label": "HSK 5"},
            {"value": 6, "label": "HSK 6"},
        ],
        "hint": "Words ≤ this level are pre-marked known during mining.",
    },
]


def get_anki_templates() -> dict:
    """Load Anki card templates from the language's anki/ directory.

    Returns a dict with keys: basic_front, basic_back, basic_css,
    cloze_front, cloze_back, cloze_css.
    """
    base = Path(__file__).parent / "anki"

    def _read(sub: str, file: str) -> str:
        path = base / sub / file
        return path.read_text() if path.exists() else ""

    return {
        "basic_front": _read("basic", "front.html"),
        "basic_back": _read("basic", "back.html"),
        "basic_css": _read("basic", "css.css"),
        "cloze_front": _read("cloze", "front.html"),
        "cloze_back": _read("cloze", "back.html"),
        "cloze_css": _read("cloze", "css.css"),
    }


# Self-register with the language factory (Open/Closed Principle).
# Adding a new language means creating a package directory with the
# same standard exports + this register_language() call — no factory edits.
register_language(
    "zh",
    name="Chinese",
    service_class=ChineseLanguageService,
    dictionary_class=CcCedictAdapter,
    frequency_class=SubtlexChAdapter,
    transcript_languages=TRANSCRIPT_LANGUAGES,
    manifest=MANIFEST,
    get_anki_templates=get_anki_templates,
    get_proficiency_level=get_proficiency_level,
    settings_schema=CHINESE_SETTINGS_SCHEMA,
)

__all__ = [
    "ChineseLanguageService",
    "CcCedictAdapter",
    "SubtlexChAdapter",
    "JiebaFrequencyAdapter",
    "get_hsk_level",
    "MANIFEST",
    "TRANSCRIPT_LANGUAGES",
    "get_proficiency_level",
    "get_anki_templates",
]
