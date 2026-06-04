"""CC-CEDICT dictionary adapter.

Implements the Dictionary port. Parses the CC-CEDICT file format:
  Traditional Simplified [pinyin] /English definition 1/German definition 2/.../

German entries are detected by checking for German-specific words in definitions.
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


class CcCedictAdapter(Dictionary):
    """CC-CEDICT dictionary lookup.

    Parses the cedict_ts.u8 file on first lookup and caches in memory.
    German definitions are auto-detected.
    """

    def __init__(self, dict_path: str | None = None):
        """Initialize the adapter.

        Args:
            dict_path: Path to cedict_ts.u8. Defaults to bundled data file.
        """
        if dict_path is None:
            # dictionary.py → chinese/ → languages/ → langmine/ → src/ → project root → data/
            dict_path = (
                Path(__file__).parent.parent.parent.parent.parent
                / "data"
                / "cedict"
                / "cedict_ts.u8"
            )
        self._dict_path = str(dict_path)
        self._entries: dict[str, dict] | None = None

    def _load(self) -> dict[str, dict]:
        """Parse the CC-CEDICT file into a lookup dict. Called lazily."""
        entries: dict[str, dict] = {}

        if not os.path.exists(self._dict_path):
            return entries

        with open(self._dict_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                # Format: Traditional Simplified [pinyin] /def1/def2/.../
                match = re.match(r"^(\S+)\s+(\S+)\s+\[(.+?)\]\s+/(.+)/$", line)
                if not match:
                    continue

                traditional, simplified, pinyin, defs_str = match.groups()
                definitions = defs_str.split("/")

                # Separate German and English definitions
                de_defs = [d for d in definitions if self._is_german(d)]
                en_defs = [d for d in definitions if not self._is_german(d)]

                entry = {
                    "pinyin": pinyin,
                    "definition_de": "; ".join(de_defs) if de_defs else "",
                    "definition_en": "; ".join(en_defs),
                }

                # Index by simplified form (preferred for lookups)
                if simplified not in entries:
                    entries[simplified] = entry
                # Also index by traditional
                if traditional != simplified:
                    entries[traditional] = entry

        return entries

    def _is_german(self, definition: str) -> bool:
        """Heuristic: check if a definition string contains German words."""
        words = set(re.findall(r"\w+", definition.lower()))
        return bool(words & _GERMAN_INDICATORS)

    def lookup(self, word: str) -> dict | None:
        """Look up a word in CC-CEDICT.

        Returns:
            Dict with keys: pinyin, definition_de, definition_en.
            None if word not found.
        """
        if self._entries is None:
            self._entries = self._load()
        return self._entries.get(word)
