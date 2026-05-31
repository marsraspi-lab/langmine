"""Chinese language extension for LangMine.

Provides:
  - ChineseLanguageService (LanguageProcessor implementation)
  - CcCedictAdapter (Dictionary implementation)
  - SubtlexChAdapter (FrequencySource implementation)
  - JiebaFrequencyAdapter (fallback FrequencySource)
  - get_hsk_level (HSK proficiency utility)
  - get_anki_templates() (Anki card templates from files)
"""

from pathlib import Path

from langmine.languages.chinese.service import ChineseLanguageService
from langmine.languages.chinese.dictionary import CcCedictAdapter
from langmine.languages.chinese.frequency import SubtlexChAdapter
from langmine.languages.chinese.jieba_frequency import JiebaFrequencyAdapter
from langmine.languages.chinese.hsk_data import get_hsk_level

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


__all__ = [
    "ChineseLanguageService",
    "CcCedictAdapter",
    "SubtlexChAdapter",
    "JiebaFrequencyAdapter",
    "get_hsk_level",
    "MANIFEST",
    "get_anki_templates",
]
