"""Tests for domain ports — verify interfaces enforce contracts."""

import pytest

from langmine.domain.ports import (
    TranscriptSource,
    AudioProcessor,
    Persistence,
    TranscriptChunk,
    MergedSentence,
)
from langmine.domain.models import Video, Sentence, VocabWord


# === TranscriptSource ===

def test_transcript_source_is_abstract():
    """TranscriptSource cannot be instantiated directly."""
    with pytest.raises(TypeError):
        TranscriptSource()  # type: ignore[abstract]


def test_transcript_source_contract():
    """Concrete implementations must implement fetch()."""

    class FakeAdapter(TranscriptSource):
        def fetch(self, video_id: str) -> list[TranscriptChunk]:
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
            self, audio_path: str, start_ms: float, end_ms: float,
            pad_before_ms: int, pad_after_ms: int,
            output_dir: str, sentence_id: str,
        ) -> str:
            return "/tmp/clip.mp3"

    adapter = FakeAdapter()
    assert adapter.download("abc", "/tmp") == "/tmp/test.mp3"
    assert adapter.clip("/tmp/a.mp3", 0, 1000, 250, 300, "/tmp", "001") == "/tmp/clip.mp3"


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

    def video_exists(self, youtube_id: str) -> bool:
        return youtube_id in self.videos

    # Sentences
    def save_sentences(self, sentences: list[Sentence]) -> None:
        for s in sentences:
            s.id = self._next_sentence_id
            self._next_sentence_id += 1
            self.sentences[s.id] = s

    def get_sentences_by_video(self, video_id: int, status: str | None = None) -> list[Sentence]:
        result = [s for s in self.sentences.values() if s.video_id == video_id]
        if status:
            result = [s for s in result if s.status == status]
        return result

    def get_stash_candidates(self, limit: int = 20) -> list[Sentence]:
        return [s for s in self.sentences.values() if s.status == "i1"][:limit]

    def update_sentence(self, sentence: Sentence) -> None:
        if sentence.id:
            self.sentences[sentence.id] = sentence

    def get_sentences_by_status(self, status: str) -> list[Sentence]:
        return [s for s in self.sentences.values() if s.status == status]

    def reclassify_stashed(self, video_id: int) -> int:
        return 0  # stub

    # Vocab
    def save_vocab_word(self, word: VocabWord) -> None:
        self.vocab[word.word_simplified] = word

    def get_vocab_word(self, word_simplified: str) -> VocabWord | None:
        return self.vocab.get(word_simplified)

    def get_known_words(self) -> set[str]:
        return {w for w, v in self.vocab.items() if v.status == "known"}

    def mark_word_known(self, word_simplified: str) -> None:
        if word_simplified in self.vocab:
            self.vocab[word_simplified].status = "known"

    def mark_word_learning(self, word_simplified: str) -> None:
        if word_simplified in self.vocab:
            self.vocab[word_simplified].status = "learning"

    def get_vocab_stats(self) -> dict:
        known = sum(1 for v in self.vocab.values() if v.status == "known")
        learning = sum(1 for v in self.vocab.values() if v.status == "learning")
        return {"known": known, "learning": learning, "total": len(self.vocab)}


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
    assert store.video_exists("abc123") is True
    assert store.video_exists("nonexistent") is False


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
        pinyin="nǐ hǎo",
        definition_de="Hallo",
        hsk_level=1,
        frequency_rank=50,
        status="known",
    )
    store.save_vocab_word(word)

    retrieved = store.get_vocab_word("你好")
    assert retrieved is not None
    assert retrieved.pinyin == "nǐ hǎo"
    assert retrieved.hsk_level == 1

    known = store.get_known_words()
    assert "你好" in known
