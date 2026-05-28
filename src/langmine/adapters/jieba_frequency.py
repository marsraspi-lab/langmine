"""Word frequency adapter using jieba's built-in dictionary.

Implements the FrequencySource port. jieba's dict.txt contains 349K entries
with word frequencies derived from general Mandarin corpora.

Frequency tier thresholds for badge display:
  🔥 Core:     rank 1–2,000
  ⭐ Useful:   rank 2,001–6,000
  💎 Rare:     rank 6,001+
"""

import os
from pathlib import Path

from langmine.domain.ports import FrequencySource


class JiebaFrequencyAdapter(FrequencySource):
    """Word frequency lookup using jieba's dictionary."""

    # Tier thresholds
    CORE_MAX = 2000
    USEFUL_MAX = 6000

    def __init__(self):
        """Load jieba's frequency dictionary."""
        self._freq: dict[str, int] = {}
        self._load()

    def _load(self):
        """Parse jieba's dict.txt: word freq tag."""
        import jieba
        dict_path = os.path.join(os.path.dirname(jieba.__file__), "dict.txt")

        with open(dict_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    word = parts[0]
                    try:
                        freq = int(parts[1])
                    except ValueError:
                        continue
                    self._freq[word] = freq

        # Convert frequencies to ranks (lower = more common)
        # Sort by frequency descending, assign rank 1 to most common
        sorted_words = sorted(self._freq.items(), key=lambda x: x[1], reverse=True)
        self._rank: dict[str, int] = {}
        for rank, (word, _) in enumerate(sorted_words, 1):
            self._rank[word] = rank

    def get_frequency(self, word: str) -> int | None:
        """Return frequency rank for a word (1 = most common).

        Returns None if word not found in jieba's dictionary.
        """
        return self._rank.get(word)

    def get_tier(self, rank: int) -> str:
        """Return the tier label for a given rank."""
        if rank <= self.CORE_MAX:
            return "core"
        elif rank <= self.USEFUL_MAX:
            return "useful"
        else:
            return "rare"

    def get_badge(self, rank: int | None) -> str:
        """Return emoji badge for a frequency rank."""
        if rank is None:
            return ""
        if rank <= self.CORE_MAX:
            return "🔥"
        elif rank <= self.USEFUL_MAX:
            return "⭐"
        else:
            return "💎"
