"""CC-CEDICT dictionary adapter.

Implements the Dictionary port. Parses the CC-CEDICT file format:
  Traditional Simplified [pinyin] /English definition 1/German definition 2/.../

German entries are detected by checking for German-specific words in definitions.
Multi-reading words (e.g. 说 shuo1/shui4) are merged into a single entry with
all readings preserved. Tone numbers are converted to diacritics (shuo1 → shuō).
"""

import os
import re
from pathlib import Path

from langmine.domain.ports import Dictionary

# Common German words used to detect German definitions
_GERMAN_INDICATORS = {
    "der",
    "die",
    "das",
    "und",
    "oder",
    "nicht",
    "sein",
    "haben",
    "werden",
    "mit",
    "auf",
    "für",
    "aus",
    "bei",
    "nach",
    "von",
    "ein",
    "eine",
    "einen",
    "einem",
    "einer",
    "des",
    "dem",
    "den",
    "sich",
    "auch",
    "als",
    "wie",
    "nur",
    "noch",
    "schon",
    "zum",
    "zur",
    "im",
    "am",
    "um",
    "über",
    "unter",
    "vor",
    "hinter",
    "neben",
    "zwischen",
    "durch",
    "gegen",
    "ohne",
    "bis",
    "aber",
    "sondern",
    "denn",
    "weil",
    "wenn",
    "dass",
    "können",
    "müssen",
    "sollen",
    "wollen",
    "dürfen",
    "mögen",
    "möchten",
    "machen",
    "tun",
    "sagen",
    "gehen",
    "kommen",
    "sehen",
    "geben",
    "wissen",
    "lassen",
    "stehen",
    "finden",
    "bleiben",
    "liegen",
    "heißen",
}

# Tone diacritic mapping for numbered→diacritic conversion
_TONE_MARKS = {
    "a": {1: "ā", 2: "á", 3: "ǎ", 4: "à", 5: "a"},
    "e": {1: "ē", 2: "é", 3: "ě", 4: "è", 5: "e"},
    "i": {1: "ī", 2: "í", 3: "ǐ", 4: "ì", 5: "i"},
    "o": {1: "ō", 2: "ó", 3: "ǒ", 4: "ò", 5: "o"},
    "u": {1: "ū", 2: "ú", 3: "ǔ", 4: "ù", 5: "u"},
    "ü": {1: "ǖ", 2: "ǘ", 3: "ǚ", 4: "ǜ", 5: "ü"},
}
_VOWELS = "aeiouü"


class CcCedictAdapter(Dictionary):
    """CC-CEDICT dictionary lookup.

    Parses the cedict_ts.u8 file on first lookup and caches in memory.
    German definitions are auto-detected. Multi-reading words are merged
    so all pronunciations are available.
    """

    def __init__(self, dict_path: str | None = None):
        if dict_path is None:
            dict_path = (
                Path(__file__).parent.parent.parent.parent.parent
                / "data"
                / "cedict"
                / "cedict_ts.u8"
            )
        self._dict_path = str(dict_path)
        self._entries: dict[str, dict] | None = None

    def _load(self) -> dict[str, dict]:
        """Parse the CC-CEDICT file into a lookup dict. Called lazily.
        Multi-reading entries are merged: all readings stored in a 'readings' list.
        """
        entries: dict[str, list[dict]] = {}
        if not os.path.exists(self._dict_path):
            return {}

        with open(self._dict_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                parsed = _parse_cedict_line(line)
                if parsed is None:
                    continue

                traditional, simplified, pinyin_numbered, definitions = parsed
                pinyin_diacritic = _numbered_to_diacritic(pinyin_numbered)
                de_defs = [d for d in definitions if self._is_german(d)]
                en_defs = [d for d in definitions if not self._is_german(d)]

                reading = {
                    "pinyin": pinyin_diacritic,
                    "pinyin_numbered": pinyin_numbered,
                    "definition_de": "; ".join(de_defs) if de_defs else "",
                    "definition_en": "; ".join(en_defs),
                }
                _index_cedict_reading(entries, traditional, simplified, reading)

        # Convert list-based entries to the enriched dict format
        return {
            word: _merge_readings(readings)
            for word, readings in entries.items()
        }

    def _is_german(self, definition: str) -> bool:
        """Heuristic: check if a definition string contains German words."""
        words = set(re.findall(r"\w+", definition.lower()))
        return bool(words & _GERMAN_INDICATORS)

    def lookup(self, word: str) -> dict | None:
        """Look up a word in CC-CEDICT.

        Returns:
            Dict with keys: pinyin (diacritics, primary reading),
            definition_de, definition_en,
            readings (list of {pinyin, pinyin_numbered, definition_de, definition_en}).
            None if word not found.
        """
        if self._entries is None:
            self._entries = self._load()
        entry = self._entries.get(word)
        if entry is not None:
            return entry
        # pypinyin fallback for words not in CC-CEDICT
        return _pypinyin_fallback(word)


# ── CC-CEDICT parsing helpers ─────────────────────────────────────────


def _parse_cedict_line(line: str) -> tuple[str, str, str, list[str]] | None:
    """Parse a CC-CEDICT line into (traditional, simplified, pinyin, definitions)."""
    match = re.match(r"^(\S+)\s+(\S+)\s+\[(.+?)\]\s+/(.+)/$", line)
    if not match:
        return None
    traditional, simplified, pinyin, defs_str = match.groups()
    definitions = defs_str.split("/")
    return traditional, simplified, pinyin, definitions


def _index_cedict_reading(
    entries: dict[str, list[dict]],
    traditional: str,
    simplified: str,
    reading: dict,
) -> None:
    """Index a reading by simplified and traditional forms.
    Accumulates readings into a list — does NOT overwrite.
    """
    key = simplified
    if key not in entries:
        entries[key] = []
    entries[key].append(reading)
    if traditional != simplified:
        if traditional not in entries:
            entries[traditional] = []
        entries[traditional].append(reading)


def _merge_readings(readings: list[dict]) -> dict:
    """Merge multiple readings into a single enriched entry.

    The first reading is treated as primary (most common).
    Returns a dict with pinyin, definition_de, definition_en,
    and a readings list of all pronunciation variants.
    """
    primary = readings[0]
    all_readings = []
    seen_pinyin = set()

    for r in readings:
        p = r["pinyin"]
        if p not in seen_pinyin:
            seen_pinyin.add(p)
            all_readings.append(dict(r))

    return {
        "pinyin": primary["pinyin"],
        "definition_de": primary["definition_de"],
        "definition_en": primary["definition_en"],
        "readings": all_readings,
    }


# ── Pinyin conversion ─────────────────────────────────────────────────


def _numbered_to_diacritic(syllable: str) -> str:
    """Convert a numbered pinyin syllable to tone-mark form.

    shuo1 → shuō, shui4 → shuì, ni3 → nǐ, ma5 → ma

    Handles multi-syllable space-separated pinyin strings.
    """
    parts = syllable.split()
    result = []
    for part in parts:
        if not part or not part[-1].isdigit():
            result.append(part)
            continue
        tone = int(part[-1])
        base = part[:-1]

        # Rule: 'a' or 'e' always take the diacritic if present
        for vowel in ("a", "e", "A", "E"):
            if vowel in base:
                idx = base.index(vowel)
                marked = _TONE_MARKS[vowel.lower()][tone]
                if vowel.isupper():
                    marked = marked.upper()
                result.append(base[:idx] + marked + base[idx + 1 :])
                break
        else:
            # 'ou' → diacritic on 'o'
            if "ou" in base:
                result.append(base.replace("o", _TONE_MARKS["o"][tone]))
            elif "Ou" in base:
                result.append(base.replace("O", _TONE_MARKS["o"][tone].upper()))
            else:
                # Diacritic on the last vowel
                vowels = [c for c in base if c.lower() in _VOWELS]
                if vowels:
                    last_vowel = vowels[-1]
                    idx = base.rfind(last_vowel)
                    marked = _TONE_MARKS.get(last_vowel.lower(), {}).get(tone, last_vowel)
                    if last_vowel.isupper():
                        marked = marked.upper()
                    result.append(base[:idx] + marked + base[idx + 1 :])
                else:
                    result.append(part)
    return " ".join(result)


def _pypinyin_fallback(word: str) -> dict | None:
    """Use pypinyin to generate a reading for a word not in CC-CEDICT.
    Only applies to words containing Chinese characters.
    """
    # Only fallback for words with Chinese characters
    if not re.search(r"[一-鿿]", word):
        return None
    try:
        from pypinyin import pinyin, Style
    except ImportError:
        return None
    py = pinyin(word, style=Style.TONE)
    if not py or not py[0]:
        return None
    diacritic = " ".join(item[0] for item in py)
    return {
        "pinyin": diacritic,
        "definition_de": "",
        "definition_en": "",
        "readings": [
            {
                "pinyin": diacritic,
                "pinyin_numbered": "",
                "definition_de": "",
                "definition_en": "",
            }
        ],
    }
