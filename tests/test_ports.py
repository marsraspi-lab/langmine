"""Tests for domain ports — verify interfaces enforce contracts."""

import pytest

from langmine.domain.models import Sentence, Video, VocabWord
from langmine.domain.ports import (
    AudioProcessor,
    Persistence,
    TranscriptChunk,
    TranscriptSource,
)

# === TranscriptSource ===


def test_transcript_source_is_abstract():
    """TranscriptSource cannot be instantiated directly."""
    with pytest.raises(TypeError):
        TranscriptSource()  # type: ignore[abstract]


def test_transcript_source_contract():
    """Concrete implementations must implement fetch()."""

    class FakeAdapter(TranscriptSource):
        def fetch(self, video_id: str, language: str = "") -> list[TranscriptChunk]:
            return []

        def list_subtitles(self, video_id: str):
            return []

    adapter = FakeAdapter()
    assert adapter.fetch("abc123") == []


# === AudioProcessor ===


def test_audio_processor_is_abstract():
    """AudioProcessor cannot be instantiated directly."""
    with pytest.raises(TypeError):
        AudioProcessor()  # type: ignore[abstract]


def test_audio_processor_contract():
    """Concrete implementations must implement download() and clip()."""

    class FakeAdapter(AudioProcessor):
        def download(self, video_id: str, output_dir: str) -> str:
            return "/tmp/test.mp3"

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
            return "/tmp/clip.mp3"

        def capture_frame(
            self,
            video_id: str,
            timestamp_ms: float,
            output_dir: str,
            sentence_id: str,
        ) -> str | None:
            return "/tmp/frame.jpg"

    adapter = FakeAdapter()
    assert adapter.download("abc", "/tmp") == "/tmp/test.mp3"
    assert (
        adapter.clip("/tmp/a.mp3", 0, 1000, 250, 300, "/tmp", "001") == "/tmp/clip.mp3"
    )


# === Persistence ===


def test_persistence_is_abstract():
    """Persistence cannot be instantiated directly."""
    with pytest.raises(TypeError):
        Persistence()  # type: ignore[abstract]


class InMemoryPersistence(Persistence):
    """Test adapter: stores everything in dicts."""

    def __init__(self):
        self.videos: dict[str, Video] = {}
        self.sentences: dict[int, Sentence] = {}
        self.vocab: dict[str, VocabWord] = {}
        self._next_sentence_id = 1

    # Videos
    def save_video(self, video: Video) -> None:
        self.videos[video.youtube_id] = video

    def get_video(self, youtube_id: str) -> Video | None:
        return self.videos.get(youtube_id)

    def list_videos(self) -> list[Video]:
        return list(self.videos.values())

    def delete_video(self, video_id: int) -> bool:
        return False  # not found in fake

    # Sentences
    def save_sentences(self, sentences: list[Sentence]) -> None:
        for s in sentences:
            s.id = self._next_sentence_id
            self._next_sentence_id += 1
            self.sentences[s.id] = s

    def get_sentences_by_video(
        self, video_id: int, status: str | None = None
    ) -> list[Sentence]:
        result = [s for s in self.sentences.values() if s.video_id == video_id]
        if status:
            result = [s for s in result if s.status == status]
        return result

    def update_sentence(self, sentence: Sentence) -> None:
        if sentence.id:
            self.sentences[sentence.id] = sentence

    def get_sentences_by_status(self, status: str) -> list[Sentence]:
        return [s for s in self.sentences.values() if s.status == status]

    # Vocab
    def save_vocab_word(self, word: VocabWord) -> None:
        self.vocab[word.word_simplified] = word

    def get_vocab_word(self, word_simplified: str) -> VocabWord | None:
        return self.vocab.get(word_simplified)

    def get_known_words(self) -> set[str]:
        return {w for w, v in self.vocab.items() if v.status in ("known", "ignored")}

    def mark_word_known(self, word_simplified: str) -> None:
        if word_simplified in self.vocab:
            self.vocab[word_simplified].status = "known"

    def mark_word_learning(self, word_simplified: str) -> None:
        if word_simplified in self.vocab:
            self.vocab[word_simplified].status = "learning"

    def mark_word_ignored(self, word_simplified: str) -> None:
        if word_simplified in self.vocab:
            self.vocab[word_simplified].status = "ignored"
        else:
            self.vocab[word_simplified] = VocabWord(
                word_simplified=word_simplified, status="ignored"
            )

    def get_vocab_stats(self) -> dict:
        known = sum(1 for v in self.vocab.values() if v.status == "known")
        learning = sum(1 for v in self.vocab.values() if v.status == "learning")
        return {"known": known, "learning": learning, "total": len(self.vocab)}

    def list_vocab(
        self, page=1, per_page=200, status=None, search=None, sort="frequency"
    ):
        words = list(self.vocab.values())
        if status:
            words = [w for w in words if w.status == status]
        if search:
            words = [
                w
                for w in words
                if search.lower() in w.word_simplified.lower()
                or search.lower() in (w.reading or "").lower()
            ]
        words.sort(key=lambda w: (w.frequency_rank is None, w.frequency_rank or 999999))
        total = len(words)
        start = (page - 1) * per_page
        return words[start : start + per_page], total

    def get_sentences_by_word(self, word: str) -> list[Sentence]:
        return [
            s
            for s in self.sentences.values()
            if s.unknown_word == word or word in s.text
        ]

    def get_sentences_by_words(
        self, words: list[str], max_per_word: int = 5
    ) -> dict[str, list[Sentence]]:
        result = {w: [] for w in words}
        for s in self.sentences.values():
            if s.unknown_word in result and len(result[s.unknown_word]) < max_per_word:
                result[s.unknown_word].append(s)
        return result

    def log_event(
        self,
        entity_type: str,
        entity_id: int,
        action: str,
        old_value: str = "",
        new_value: str = "",
        language_code: str = "",
    ) -> None:
        pass


def test_in_memory_persistence_roundtrip():
    """Save and retrieve a video through the Persistence port."""
    store = InMemoryPersistence()

    video = Video(
        youtube_id="abc123",
        title="Test Video",
        channel="Test Channel",
        duration_sec=120,
        transcript_json="[]",
        audio_path="/tmp/test.mp3",
    )
    store.save_video(video)

    retrieved = store.get_video("abc123")
    assert retrieved is not None
    assert retrieved.title == "Test Video"
    assert retrieved.youtube_id == "abc123"
    assert store.get_video("abc123") is not None
    assert store.get_video("nonexistent") is None


def test_in_memory_persistence_sentences():
    """Save and query sentences through the Persistence port."""
    store = InMemoryPersistence()

    sentence = Sentence(
        video_id=1,
        start_ms=0,
        end_ms=1000,
        text="你好世界",
        text_segmented="你好 世界",
        status="i1",
        unknown_word="世界",
        unknown_word_rank=500,
        audio_clip_path="/tmp/clip.mp3",
        screenshot_path="/tmp/img.jpg",
        screenshot_enabled=True,
    )
    store.save_sentences([sentence])

    results = store.get_sentences_by_video(1, status="i1")
    assert len(results) == 1
    assert results[0].text == "你好世界"
    assert results[0].unknown_word == "世界"


def test_in_memory_persistence_vocab():
    """Save and query vocabulary through the Persistence port."""
    store = InMemoryPersistence()

    word = VocabWord(
        word_simplified="你好",
        reading="nǐ hǎo",
        definition_de="Hallo",
        hsk_level=1,
        frequency_rank=50,
        status="known",
    )
    store.save_vocab_word(word)

    retrieved = store.get_vocab_word("你好")
    assert retrieved is not None
    assert retrieved.reading == "nǐ hǎo"
    assert retrieved.hsk_level == 1

    known = store.get_known_words()
    assert "你好" in known
