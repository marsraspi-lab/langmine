"""Domain ports — interfaces that domain logic depends on.

Every external system (YouTube, ffmpeg, SQLite, Google Translate, AnkiConnect)
is accessed through these ports. Adapters implement them.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from langmine.domain.models import Video, Sentence, VocabWord


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


# === Ports ===


class TranscriptSource(ABC):
    """Port for fetching video subtitles.

    Adapters: YouTubeTranscriptApi, NetflixSRT, manual upload.
    """

    @abstractmethod
    def fetch(self, video_id: str) -> list[TranscriptChunk]:
        """Fetch subtitle chunks for a video.

        Raises:
            ValueError: If the video is unavailable or has no transcript.
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


class Persistence(ABC):
    """Port for storing and retrieving all application state.

    Adapters: SQLite, JSON files, in-memory dicts (tests).
    Domain code never touches SQL directly — only this interface.

    Swap SQLite for a filesystem adapter without changing any domain code.
    """

    # Videos
    @abstractmethod
    def save_video(self, video: Video) -> None: ...
    @abstractmethod
    def get_video(self, youtube_id: str) -> Video | None: ...
    @abstractmethod
    def list_videos(self) -> list[Video]: ...
    @abstractmethod
    def video_exists(self, youtube_id: str) -> bool: ...

    # Sentences
    @abstractmethod
    def save_sentences(self, sentences: list[Sentence]) -> None: ...
    @abstractmethod
    def get_sentences_by_video(self, video_id: int, status: str | None = None) -> list[Sentence]: ...
    @abstractmethod
    def get_stash_candidates(self, limit: int = 20) -> list[Sentence]: ...
    @abstractmethod
    def update_sentence(self, sentence: Sentence) -> None: ...
    @abstractmethod
    def get_sentences_by_status(self, status: str) -> list[Sentence]: ...
    @abstractmethod
    def reclassify_stashed(self, video_id: int) -> int:
        """Re-classify stashed sentences after vocab change. Returns count of newly-i+1."""
        ...

    # Vocab
    @abstractmethod
    def save_vocab_word(self, word: VocabWord) -> None: ...
    @abstractmethod
    def get_vocab_word(self, word_simplified: str) -> VocabWord | None: ...
    @abstractmethod
    def get_known_words(self) -> set[str]: ...
    @abstractmethod
    def mark_word_known(self, word_simplified: str) -> None: ...
    @abstractmethod
    def mark_word_learning(self, word_simplified: str) -> None: ...
    @abstractmethod
    def get_vocab_stats(self) -> dict: ...


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
