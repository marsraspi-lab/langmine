"""Domain ports — interfaces that domain logic depends on.

Every external system (YouTube, ffmpeg, SQLite, Google Translate, AnkiConnect)
is accessed through these ports. Adapters implement them.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from langmine.domain.models import Sentence, Video, VocabWord

# === Value Objects (used across ports) ===


@dataclass
class TranscriptChunk:
    """A single subtitle chunk with timing."""

    text: str
    start_ms: float
    duration_ms: float


@dataclass
class MergedSentence:
    """A merged sentence with timing boundaries."""

    text: str
    start_ms: float
    end_ms: float


@dataclass
class SubtitleInfo:
    """Info about an available subtitle track."""

    language_code: str  # e.g. "zh-Hans", "en"
    language_name: str  # e.g. "Chinese (Simplified)", "English"
    kind: str  # "manual" or "auto"


# === Ports ===


class LanguageProcessor(ABC):
    """Abstract base for language-specific NLP processing.

    This is a DOMAIN PORT — domain code talks to this interface.
    Each language (Chinese, Spanish, Korean, Russian, etc.) provides
    a domain service that implements this port.

    The implementation injects lower-level ports (Dictionary, Translator,
    FrequencySource) — it never calls external systems directly.
    """

    @abstractmethod
    def segment(self, text: str) -> list[str]:
        """Segment text into words/tokens."""

    @abstractmethod
    def get_reading(self, text: str) -> str:
        """Phonetic reading: pinyin for zh, IPA for es, etc."""

    @abstractmethod
    def lookup_word(self, word: str) -> dict | None:
        """Dictionary lookup. Returns definition dict with keys
        'definition_de' and 'definition_en'. None if not found."""

    @abstractmethod
    def translate_sentence(self, text: str) -> str:
        """Sentence-level MT. Returns German translation."""

    @abstractmethod
    def get_frequency(self, word: str) -> int | None:
        """Frequency rank (lower = more common). None if unknown."""

    @abstractmethod
    def is_non_word(self, token: str) -> bool:
        """True if this token should be excluded from i+1 counting
        (particles, numbers, names, etc.)."""

    @abstractmethod
    def is_proper_name(self, token: str, context_sentence: str = "") -> bool:
        """True if token is a proper name (person, place, etc.).

        When context_sentence is provided, implementations SHOULD use
        sentence-level POS tagging on the full sentence to avoid
        sub-segmentation of multi-character names.

        Proper names should be visually distinguished in the
        transcript and excluded from i+1 unknown counting.
        """

    @abstractmethod
    def find_known_synonyms(self, word: str, known_words: set[str]) -> list[str]:
        """Return any known synonyms of `word`."""

    @abstractmethod
    def get_annotation(self, text: str) -> str:
        """Return JSON string of character-level annotations.

        For CJK: [{char, pinyin, tone}] per character (Pleco tone colors 1-5).
        For other languages: may return "[]" or language-specific annotations.
        """

    def bootstrap_proficiency(
        self,
        persistence: "Persistence",
        max_level: int,
        language_code: str,
    ) -> None:
        """Pre-mark words from a proficiency framework as known.

        Called once per video during mining. The implementation decides which
        proficiency framework to use (HSK for Chinese, JLPT for Japanese, etc.)
        and marks words at or below max_level as known in the vocabulary.

        Default: no-op. Override in language-specific services.
        Args:
            persistence: Vocab persistence to mark words.
            max_level: Maximum proficiency level to bootstrap (e.g. 3 = HSK 1-3).
                No-op when <= 0.
            language_code: Language to scope the bootstrap to (e.g. 'zh').
        """
        return  # default no-op


class TranscriptSource(ABC):
    """Port for fetching video subtitles.

    Adapters: YouTubeTranscriptApi, NetflixSRT, manual upload.
    """

    @abstractmethod
    def fetch(self, video_id: str, language: str = "") -> list[TranscriptChunk]:
        """Fetch subtitle chunks for a video.

        Args:
            video_id: YouTube video ID or URL.
            language: Optional subtitle language code (e.g., 'zh-Hans').
                When provided, download this specific language track.
                When empty, use the adapter's default language preferences.

        Raises:
            ValueError: If the video is unavailable or has no transcript.
        """

    @abstractmethod
    def list_subtitles(self, video_id: str) -> list[SubtitleInfo]:
        """Return available subtitle tracks for a video.

        Returns empty list if no subtitles exist.
        Raises ValueError if the video is unavailable/private.
        """


class AudioProcessor(ABC):
    """Port for audio download and clipping.

    Adapters: yt-dlp+ffmpeg, local audio file.
    """

    @abstractmethod
    def download(self, video_id: str, output_dir: str) -> str:
        """Download full audio for a video. Returns file path.

        Should skip if already cached at output_dir/video_id.mp3.
        """

    @abstractmethod
    def clip(
        self,
        audio_path: str,
        start_ms: float,
        end_ms: float,
        pad_before_ms: int,
        pad_after_ms: int,
        output_dir: str,
        sentence_id: str,
    ) -> str:
        """Extract a segment from audio. Returns path to clip."""

    @abstractmethod
    def capture_frame(
        self,
        video_id: str,
        timestamp_ms: float,
        output_dir: str,
        sentence_id: str,
    ) -> str | None:
        """Capture a video frame as JPEG. Returns path or None on failure."""


class Persistence(ABC):
    """Port for storing and retrieving all application state.

    Adapters: SQLite, JSON files, in-memory dicts (tests).
    Domain code never touches SQL directly — only this interface.

    Swap SQLite for a filesystem adapter without changing any domain code.

    Query methods accept an optional language_code to scope results.
    When empty, returns all languages (debug/migration). When set, filters by it.
    """

    # Videos
    @abstractmethod
    def save_video(self, video: Video) -> None: ...
    @abstractmethod
    def get_video(self, youtube_id: str) -> Video | None: ...
    @abstractmethod
    def list_videos(self, language_code: str = "") -> list[Video]: ...
    @abstractmethod
    def delete_video(self, video_id: int) -> bool:
        """Delete a video and all related data (sentences, events).

        Returns True if a video was deleted, False if not found.
        """
        ...

    # Sentences
    @abstractmethod
    def save_sentences(self, sentences: list[Sentence]) -> None: ...
    @abstractmethod
    def get_sentences_by_video(
        self, video_id: int, status: str | None = None, language_code: str = ""
    ) -> list[Sentence]: ...
    @abstractmethod
    def update_sentence(self, sentence: Sentence) -> None: ...
    @abstractmethod
    def get_sentences_by_status(
        self, status: str, language_code: str = ""
    ) -> list[Sentence]: ...

    # Vocab
    @abstractmethod
    def save_vocab_word(self, word: VocabWord) -> None: ...
    @abstractmethod
    def get_vocab_word(self, word_simplified: str) -> VocabWord | None: ...
    @abstractmethod
    def get_known_words(self, language_code: str = "") -> set[str]: ...
    @abstractmethod
    def mark_word_known(self, word_simplified: str) -> None: ...
    @abstractmethod
    def mark_word_learning(self, word_simplified: str) -> None: ...
    @abstractmethod
    def mark_word_ignored(self, word_simplified: str) -> None: ...

    @abstractmethod
    def get_vocab_stats(self, language_code: str = "") -> dict: ...

    @abstractmethod
    def list_vocab(
        self,
        page: int = 1,
        per_page: int = 200,
        status: str | None = None,
        search: str | None = None,
        sort: str = "frequency",
        language_code: str = "",
    ) -> tuple[list[VocabWord], int]:
        """Paginated vocabulary list.

        Args:
            page: 1-indexed page number.
            per_page: Items per page (default 200).
            status: Filter by status ('known', 'learning', or None for all).
            search: Filter by word or reading substring.
            sort: Sort order — 'frequency' (asc), 'hsk' (asc), or 'recent' (desc).
            language_code: Language filter (e.g. 'zh', 'es'). Empty = all languages.

        Returns:
            (list of VocabWord, total_count).
        """
        ...

    @abstractmethod
    def get_sentences_by_word(self, word: str) -> list[Sentence]:
        """Return all sentences containing a given word.

        Matches against unknown_word field and text field.
        """
        ...

    @abstractmethod
    def log_event(
        self,
        entity_type: str,
        entity_id: int,
        action: str,
        old_value: str = "",
        new_value: str = "",
        language_code: str = "",
    ) -> None:
        """Append an immutable event to the timeline log.

        Events are append-only — never updated or deleted.
        Used for timeline visualization and vocab progress tracking.
        """
        ...


class Translator(ABC):
    """Port for sentence-level machine translation.

    Adapters: Google Translate, DeepL.
    """

    @abstractmethod
    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """Translate text. Returns translated string."""


class Dictionary(ABC):
    """Port for word-level dictionary lookup.

    Adapters: CC-CEDICT, custom dictionary.
    """

    @abstractmethod
    def lookup(self, word: str) -> dict | None:
        """Look up a word. Returns dict with definition_de, definition_en, pinyin.
        Returns None if word not found.
        """


class FrequencySource(ABC):
    """Port for word frequency data.

    Adapters: SUBTLEX-CH (Chinese), SUBTLEX-UK (English), custom frequency lists.
    """

    @abstractmethod
    def get_frequency(self, word: str) -> int | None:
        """Return frequency rank for a word (lower = more common).
        Returns None if unknown.
        """


class AnkiExporter(ABC):
    """Port for exporting sentences as Anki flashcards.

    Adapters: AnkiConnect (HTTP API to running Anki), genanki (.apkg file).
    """

    @abstractmethod
    def export(
        self,
        sentences: list,
        deck_name: str = "Chinese::Sentence Mining",
        note_type_name: str = "LangMine Sentence",
    ) -> dict:
        """Export sentences to Anki.

        Args:
            sentences: List of Sentence domain objects.
            deck_name: Anki deck name (created if missing).
            note_type_name: Anki note type (created if missing).

        Returns:
            Dict with: note_ids (list[int]), added (int),
            duplicates (int), errors (list[str]).
        """


class ImageSearch(ABC):
    """Port for image search by word/query.

    Adapters: Google Custom Search, Bing Image Search.
    """

    @abstractmethod
    def search(self, query: str, count: int = 5) -> list[str]:
        """Return list of image URLs for a query.

        Args:
            query: Search query (e.g., Chinese word + context).
            count: Number of image URLs to return (default 5).

        Returns:
            List of image URLs.
        """
