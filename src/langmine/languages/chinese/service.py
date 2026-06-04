"""Chinese language service — domain logic for Chinese NLP.

Implements the LanguageProcessor port using injected ports:
  Dictionary → CC-CEDICT (adapter) or fake (tests)
  Translator → Google Translate (adapter) or fake (tests)
  FrequencySource → SUBTLEX-CH (adapter) or fake (tests)

Pure methods (segment, get_reading, is_non_word) use in-memory
algorithms and require no ports.
"""

import re

import jieba
import pypinyin

from langmine.domain.ports import (
    Dictionary,
    FrequencySource,
    LanguageProcessor,
    Translator,
)

# Particles and function words that should NOT count as words for i+1
CHINESE_PARTICLES = {
    "的",
    "了",
    "吗",
    "吧",
    "呢",
    "啊",
    "哦",
    "嗯",
    "嘛",
    "啦",
    "呀",
    "呗",
    "咯",
    "哈",
    "哇",
    "哎",
    "唉",
    "哟",
    "着",
    "过",
    "地",
    "得",
}


class ChineseLanguageService(LanguageProcessor):
    """Chinese NLP — depends on ports, never on concrete adapters."""

    def __init__(
        self,
        dictionary: Dictionary,
        translator: Translator,
        frequency: FrequencySource,
    ):
        self._dict = dictionary
        self._translator = translator
        self._frequency = frequency

    # === Pure domain logic (no ports needed) ===

    def segment(self, text: str) -> list[str]:
        """Segment Chinese text using jieba (pure in-memory)."""
        return list(jieba.cut(text))

    def get_reading(self, text: str) -> str:
        """Generate pinyin using pypinyin (pure in-memory)."""
        return " ".join(pypinyin.lazy_pinyin(text))

    def is_non_word(self, token: str) -> bool:
        """True if token should be excluded from i+1 counting.

        Filters out: particles, numbers, dates, proper names.
        """
        # Particles
        if token in CHINESE_PARTICLES:
            return True

        # Pure numbers
        if re.match(r"^\d+$", token):
            return True

        # Chinese numeral (standalone digit-words are not content words)
        if token in {
            "零",
            "一",
            "二",
            "三",
            "四",
            "五",
            "六",
            "七",
            "八",
            "九",
            "十",
            "百",
            "千",
            "万",
            "亿",
            "两",
        }:
            return True

        # Dates and number patterns: 2024年, 三月, 七点, 第X
        if re.match(r"^\d+年$", token):
            return True
        if re.match(r"^[零一二三四五六七八九十百千万亿]+[月日点分秒]$", token):
            return True
        if re.match(r"^第[零一二三四五六七八九十百千万亿\d]+$", token):
            return True

        return False

    # Proper name POS tags (jieba posseg)
    PROPER_NAME_TAGS = frozenset(
        {
            "nr",  # person name (e.g., 曹操, 刘备)
            "ns",  # place name (e.g., 北京, 长安)
            "nrfg",  # person name — given name
            "nrt",  # person name — transliterated
        }
    )

    def is_proper_name(self, token: str, context_sentence: str = "") -> bool:
        """Detect proper names via jieba POS tagging.

        When context_sentence is provided, uses sentence-level pseg.cut()
        and matches the token by position to avoid sub-segmentation of
        multi-character names (e.g., 李世民 → 李 + 世民 instead of 李世民).
        """
        import jieba.posseg as pseg

        if context_sentence:
            # Sentence-level POS: segment the full sentence, match token by position
            for word, flag in pseg.cut(context_sentence):
                if word == token and flag in self.PROPER_NAME_TAGS:
                    return True
            return False
        else:
            # Fallback: token-level POS (may sub-segment multi-char names)
            for word, flag in pseg.cut(token):
                if word == token and flag in self.PROPER_NAME_TAGS:
                    return True
            return False

    # === Port-delegated methods (depend on injected ports) ===

    def lookup_word(self, word: str) -> dict | None:
        """Look up word through the Dictionary port."""
        return self._dict.lookup(word)

    def translate_sentence(self, text: str) -> str:
        """Translate sentence through the Translator port."""
        return self._translator.translate(text, source_lang="zh", target_lang="de")

    def get_frequency(self, word: str) -> int | None:
        """Get frequency rank through the FrequencySource port."""
        return self._frequency.get_frequency(word)

    def find_known_synonyms(self, word: str, known_words: set[str]) -> list[str]:
        """Detect known synonyms via Dictionary port.

        Checks the word's CC-CEDICT definition for 'same as X' / 'see also X'
        patterns and returns any that are in the known_words set.
        """
        entry = self._dict.lookup(word)
        if entry is None:
            return []

        # Search for synonym patterns in the English definition
        definition = entry.get("definition_en", "")
        synonyms = set()

        # Pattern: "same as X" / "see also X" / "also written X" / "variant of X"
        # X can be English (\w+) or Chinese (CJK characters)
        patterns = [
            r"same as ([\w\u4e00-\u9fff]+)",
            r"see also ([\w\u4e00-\u9fff]+)",
            r"also written ([\w\u4e00-\u9fff]+)",
            r"variant of ([\w\u4e00-\u9fff]+)",
        ]

        for pattern in patterns:
            for match in re.findall(pattern, definition, re.IGNORECASE):
                # Check if the matched word (English or Chinese) is in known_words
                if match in known_words:
                    synonyms.add(match)

        return list(synonyms)

    def get_annotation(self, text: str) -> str:
        """Return JSON of [{char, pinyin, tone}] per character.

        Uses pypinyin with TONE3 style for tone numbers.
        Pleco tone colors: 1=red, 2=green, 3=blue, 4=purple, 5=gray.
        """
        import json as _json

        from pypinyin import Style, pinyin

        py_list = pinyin(text, style=Style.TONE3)
        entries = []
        for i, char in enumerate(text):
            py_with_tone = py_list[i][0] if i < len(py_list) else ""
            # Extract tone number (last digit of pinyin string)
            tone = 5  # neutral default
            if py_with_tone and py_with_tone[-1].isdigit():
                tone = int(py_with_tone[-1])
                pinyin_str = py_with_tone[:-1]
            else:
                pinyin_str = py_with_tone or char

            entries.append(
                {
                    "char": char,
                    "pinyin": pinyin_str,
                    "tone": tone,
                }
            )
        return _json.dumps(entries)

    def bootstrap_proficiency(
        self,
        persistence,
        max_level: int,
        language_code: str,
    ) -> None:
        """Pre-mark HSK words up to max_level as known (M21).

        Only marks words that don't already exist in the vocab table —
        respects user modifications to existing words.  A no-op when
        max_level is 0 or the HSK data file is missing.
        """
        if max_level < 1:
            return

        import json as _json
        from pathlib import Path

        from langmine.domain.models import VocabWord

        # service.py → chinese/ → languages/ → langmine/ → src/ → project root
        hsk_path = (
            Path(__file__).resolve().parents[4] / "data" / "hsk" / "hsk_levels.json"
        )
        if not hsk_path.exists():
            return

        with open(hsk_path, encoding="utf-8") as f:
            hsk_words: dict[str, int] = _json.load(f)

        for word, word_level in hsk_words.items():
            if word_level > max_level:
                continue
            existing = persistence.get_vocab_word(word)
            if existing is not None:
                continue  # Don't overwrite user modifications
            persistence.save_vocab_word(
                VocabWord(
                    word_simplified=word,
                    hsk_level=word_level,
                    status="known",
                    language_code=language_code,
                )
            )
