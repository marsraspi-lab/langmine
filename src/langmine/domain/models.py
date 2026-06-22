"""Domain models — pure dataclasses with no I/O dependencies.

These are the core concepts of LangMine. They contain no database logic,
no API calls, no file system access. Just data and domain rules.
"""

from dataclasses import dataclass

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
    transcript_json: str = ""  # raw transcript JSON
    audio_path: str = ""  # path to full MP3
    processed_at: str | None = None
    language_code: str = ""  # "zh", "es", "ko", etc.
    subtitle_language: str = ""  # e.g. "zh-Hans" — chosen subtitle track
    subtitle_kind: str = ""  # "manual", "auto", or ""
    target_subtitle_language: str = ""  # e.g. "de" — translation subtitle track
    target_subtitle_kind: str = ""  # "manual", "auto", or ""
    target_transcript_json: str = ""  # raw JSON of target transcript chunks

    # Set by persistence layer
    id: int | None = None


@dataclass
class Sentence:
    """A single extracted sentence from a video."""

    video_id: int
    start_ms: float
    end_ms: float
    text: str
    text_segmented: str = ""  # "我们 / 一般 / 早上 / 七点 / 起床"
    non_words_json: str = ""  # JSON list of filtered-out tokens
    reading: str = ""  # Phonetic: pinyin for zh, IPA for es, romanization for ko
    translation: str = ""  # German translation
    unknown_word: str | None = None  # the i+1 target word
    unknown_word_rank: int | None = None
    known_synonyms_json: str = ""  # JSON list of known synonyms
    audio_clip_path: str = ""
    screenshot_path: str = ""
    screenshot_enabled: bool = True
    cloze_image_url: str | None = None  # User-selected image for cloze hint
    annotation_json: str = ""  # Character-level annotations (ruby for CJK, IPA, etc.)
    status: str = "new"  # i1 | i0 | stashed | kept | deleted | exported
    language_code: str = ""  # "zh", "es", "ko", etc.
    created_at: str = ""  # ISO 8601 — when sentence was first extracted
    updated_at: str = ""  # ISO 8601 — when status last changed

    # Set by persistence layer
    id: int | None = None


@dataclass
class VocabWord:
    """A word in the user's vocabulary."""

    word_simplified: str
    word_traditional: str = ""
    reading: str = ""
    definition_de: str = ""
    hsk_level: int | None = None  # 1-6 or None if not in HSK
    frequency_rank: int | None = None  # from SUBTLEX-CH
    status: str = "known"  # known | learning
    language_code: str = ""  # "zh", "es", "ko", etc.
    created_at: str = ""  # ISO 8601 — when word was first added
    updated_at: str = ""  # ISO 8601 — when status last changed

    # Set by persistence layer
    id: int | None = None


@dataclass
class Event:
    """An immutable record of a state-changing action for timeline visualization.

    Events are append-only — never updated or deleted.
    """

    entity_type: str  # "video" | "sentence" | "word"
    entity_id: int  # FK to videos.id / sentences.id / vocab.id
    action: str  # "mined" | "classified_i1" | "kept" | "deleted" | ...
    old_value: str = ""  # previous status (or empty if not applicable)
    new_value: str = ""  # new status (or key detail)
    timestamp: str = ""  # ISO 8601 — set by persistence layer
    language_code: str = ""

    # Set by persistence layer
    id: int | None = None
