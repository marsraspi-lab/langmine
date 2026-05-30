"""HSK level lookup.

Loads the bundled HSK 2.0 word list (old 6-level system) from
data/hsk/hsk_levels.json. Not an adapter — pure data lookup with
no external dependencies. Safe to import from any layer.
"""

import json
from pathlib import Path

_HSK: dict[str, int] | None = None


def _load() -> dict[str, int]:
    global _HSK
    if _HSK is not None:
        return _HSK

    # hsk_data.py → chinese/ → languages/ → langmine/ → src/ → project root → data/hsk/
    path = (
        Path(__file__).resolve().parent.parent.parent.parent.parent
        / "data" / "hsk" / "hsk_levels.json"
    )
    with open(path, encoding="utf-8") as f:
        _HSK = json.load(f)
    return _HSK


def get_hsk_level(word: str) -> int | None:
    """Return HSK level (1-6) for a word, or None if not in HSK.

    Args:
        word: Simplified Chinese word to look up.

    Returns:
        HSK level 1–6, or None.
    """
    return _load().get(word)
