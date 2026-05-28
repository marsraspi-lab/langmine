"""SUBTLEX-CH frequency adapter.

Implements the FrequencySource port using the SUBTLEX-CH-WF corpus.
SUBTLEX-CH is a word frequency database from Chinese film/TV subtitles
(99,124 entries, GB18030 encoding). It's the gold standard for spoken
Chinese frequency data — much better matched to YouTube content than
general-purpose corpora like jieba's built-in dictionary.

Columns: Word, WCount, W/million, logW, W-CD, W-CD%, logW-CD

File source: https://doi.org/10.1371/journal.pone.0010729.s002
"""

from pathlib import Path

from langmine.domain.ports import FrequencySource


_DATA_PATH = Path(__file__).parent.parent.parent.parent / "data" / "SUBTLEX-CH-WF"

# Frequency tier thresholds
CORE_MAX = 2000
USEFUL_MAX = 6000


class SubtlexChAdapter(FrequencySource):
    """Word frequency using SUBTLEX-CH subtitle corpus."""

    def __init__(self, data_path: str | Path | None = None):
        """Load the SUBTLEX-CH-WF frequency list.

        Args:
            data_path: Path to SUBTLEX-CH-WF file. Defaults to data/SUBTLEX-CH-WF
                       relative to the project root.
        """
        self._data_path = Path(data_path) if data_path else _DATA_PATH
        self._rank: dict[str, int] = {}
        self._load()

    def _load(self):
        """Parse SUBTLEX-CH-WF into an in-memory rank dict.

        The file is GB18030-encoded, tab-separated.
        First 3 lines are metadata/header — skip them.
        Sort by W/million descending, assign rank 1 to most frequent word.
        """
        with open(self._data_path, encoding="gb18030") as f:
            lines = f.readlines()

        # Build (word, wpm) list, skipping metadata + header (lines 0-2)
        entries: list[tuple[str, float]] = []
        for line in lines[3:]:
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            word = parts[0]
            try:
                wpm = float(parts[2])
            except ValueError:
                continue
            entries.append((word, wpm))

        # Sort by W/million descending (most common first)
        entries.sort(key=lambda x: x[1], reverse=True)

        # Assign ranks: rank 1 = most common
        self._rank = {word: i + 1 for i, (word, _) in enumerate(entries)}

    def get_frequency(self, word: str) -> int | None:
        """Return frequency rank (1 = most common, lower = more frequent).

        Returns None if the word is not in SUBTLEX-CH.
        """
        return self._rank.get(word)

    @property
    def total_entries(self) -> int:
        """Number of entries in the frequency list."""
        return len(self._rank)

    @staticmethod
    def get_tier(rank: int) -> str:
        """Return tier label for a given rank."""
        if rank <= CORE_MAX:
            return "core"
        elif rank <= USEFUL_MAX:
            return "useful"
        else:
            return "rare"

    @staticmethod
    def get_badge(rank: int | None) -> str:
        """Return emoji badge for a frequency rank."""
        if rank is None:
            return ""
        if rank <= CORE_MAX:
            return "🔥"
        elif rank <= USEFUL_MAX:
            return "⭐"
        else:
            return "💎"
