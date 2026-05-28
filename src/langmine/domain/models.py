"""Domain models — pure dataclasses with no I/O dependencies.

These are the core concepts of LangMine. They contain no database logic,
no API calls, no file system access. Just data and domain rules.
"""

from dataclasses import dataclass, field
from datetime import datetime


# === Frequency Rank (domain logic, no I/O) ===

# Tier thresholds — same for any frequency source (SUBTLEX-CH, jieba, etc.)
_CORE_MAX = 2000
_USEFUL_MAX = 6000


def frequency_tier(rank: int) -> str:
    """Return tier label for a frequency rank (1 = most common)."""
    if rank <= _CORE_MAX:
        return "core"
    elif rank <= _USEFUL_MAX:
        return "useful"
    else:
        return "rare"


def frequency_badge(rank: int | None) -> str:
    """Return emoji badge for a frequency rank."""
    if rank is None:
        return ""
    if rank <= _CORE_MAX:
        return "🔥"
    elif rank <= _USEFUL_MAX:
        return "⭐"
    else:
        return "💎"


@dataclass
class Video:
    """A YouTube video that has been or will be mined."""

    youtube_id: str
    title: str = ""
    channel: str = ""
    duration_sec: int = 0
    transcript_json: str = ""     # raw transcript JSON
    audio_path: str = ""           # path to full MP3
    processed_at: str | None = None

    # Set by persistence layer
    id: int | None = None


@dataclass
class Sentence:
    """A single extracted sentence from a video."""

    video_id: int
    start_ms: float
    end_ms: float
    text: str
    text_segmented: str = ""        # "我们 / 一般 / 早上 / 七点 / 起床"
    non_words_json: str = ""        # JSON list of filtered-out tokens
    pinyin: str = ""                # "wǒmen yībān zǎoshang..."
    translation_de: str = ""        # German translation
    unknown_word: str | None = None  # the i+1 target word
    unknown_word_rank: int | None = None
    known_synonyms_json: str = ""   # JSON list of known synonyms
    audio_clip_path: str = ""
    screenshot_path: str = ""
    screenshot_enabled: bool = True
    status: str = "new"            # i1 | i0 | stashed | kept | deleted | exported

    # Set by persistence layer
    id: int | None = None


@dataclass
class VocabWord:
    """A word in the user's vocabulary."""

    word_simplified: str
    word_traditional: str = ""
    pinyin: str = ""
    definition_de: str = ""
    hsk_level: int | None = None      # 1-6 or None if not in HSK
    frequency_rank: int | None = None  # from SUBTLEX-CH
    status: str = "known"             # known | learning

    # Set by persistence layer
    id: int | None = None
