"""Tests for process_video() — full video mining with classification."""

import pytest

from langmine.pipeline import process_video
from langmine.domain.ports import (
    TranscriptSource, AudioProcessor, Persistence, MergedSentence,
    LanguageProcessor, Dictionary, Translator, FrequencySource,
)
from langmine.domain.models import Video, Sentence


# === Fake ports with Chinese NLP ===


class FakeChineseProcessor(LanguageProcessor):
    """Returns predictable Chinese segmentation and frequency."""

    def segment(self, text: str) -> list[str]:
        return text.split()

    def get_reading(self, text: str) -> str:
        return text

    def lookup_word(self, word: str) -> dict | None:
        return {"definition_de": f"def:{word}", "definition_en": f"def:{word}"}

    def translate_sentence(self, text: str) -> str:
        return f"[DE] {text}"

    def get_frequency(self, word: str) -> int | None:
        ranks = {"一般": 1847, "效率": 3412}
        return ranks.get(word)

    def is_non_word(self, token: str) -> bool:
        return token in {"的", "了", "吗"}

    def find_known_synonyms(self, word: str, known_words: set[str]) -> list[str]:
        return []


class FakeTranscript(TranscriptSource):
    def __init__(self, chunks):
        from langmine.domain.ports import TranscriptChunk
        # Spread chunks apart so they don't merge (1000ms gap between sentences)
        self.chunks = [TranscriptChunk(text=t, start_ms=i * 2000, duration_ms=1000)
                       for i, t in enumerate(chunks)]

    def fetch(self, video_id: str):
        return self.chunks


class FakeAudio(AudioProcessor):
    def download(self, video_id: str, output_dir: str) -> str:
        return f"{output_dir}/test.mp3"

    def clip(self, audio_path, start_ms, end_ms, pad_before, pad_after, output_dir, sentence_id):
        return f"{output_dir}/sentence_{sentence_id}.mp3"


class FakePersistence(Persistence):
    def __init__(self, known_words: set[str] | None = None):
        self._known = known_words or set()
        self.videos: dict = {}
        self.sentences: list[Sentence] = []

    def get_known_words(self) -> set[str]:
        return self._known

    def save_video(self, video):
        if video.id is None:
            video.id = len(self.videos) + 1
        self.videos[video.youtube_id] = video
    def get_video(self, yt_id): return self.videos.get(yt_id)
    def list_videos(self): return list(self.videos.values())
    def video_exists(self, yt_id): return yt_id in self.videos

    def save_sentences(self, sentences):
        for s in sentences:
            s.id = len(self.sentences) + 1
            self.sentences.append(s)

    def get_sentences_by_video(self, vid, status=None):
        result = [s for s in self.sentences if s.video_id == vid]
        if status:
            result = [s for s in result if s.status == status]
        return result

    def get_stash_candidates(self, limit=20): return []
    def update_sentence(self, s): pass
    def get_sentences_by_status(self, status): return []
    def reclassify_stashed(self, vid): return 0
    def save_vocab_word(self, w): pass
    def get_vocab_word(self, w): return None
    def mark_word_known(self, w): pass
    def mark_word_learning(self, w): pass
    def get_vocab_stats(self): return {"known": 0, "learning": 0, "total": 0}


# === Tests ===


def test_process_video_saves_video():
    """process_video should save the video in persistence."""
    transcript = FakeTranscript(["你好世界", "我很好"])
    audio = FakeAudio()
    persistence = FakePersistence(known_words={"我", "很好", "你", "好", "世界"})
    processor = FakeChineseProcessor()

    result = process_video(
        transcript_source=transcript,
        audio_processor=audio,
        persistence=persistence,
        language_processor=processor,
        video_id="test123",
        output_dir="/tmp/test",
    )

    assert persistence.video_exists("test123")
    video = persistence.get_video("test123")
    assert video.title == "test123"


def test_process_video_classifies_sentences():
    """process_video should classify sentences as i1/i0/stashed."""
    transcript = FakeTranscript(["我们 一般 学习", "我 爱 你"])
    audio = FakeAudio()
    persistence = FakePersistence(known_words={"我们", "学习", "我", "爱", "你"})
    processor = FakeChineseProcessor()

    result = process_video(
        transcript_source=transcript,
        audio_processor=audio,
        persistence=persistence,
        language_processor=processor,
        video_id="test456",
        output_dir="/tmp/test",
    )

    # "我们 一般 学习" — "一般" unknown → i1
    i1 = result["i1_candidates"]
    assert len(i1) == 1
    assert i1[0].unknown_word == "一般"

    # "我 爱 你" — all known → i0
    i0_count = result["i0_count"]
    assert i0_count == 1


def test_process_video_applies_cap():
    """process_video should respect max_cards for i+1 candidates."""
    # Create 25 sentences each with one unique unknown word
    texts = [f"我们 word{i} 学习" for i in range(25)]
    transcript = FakeTranscript(texts)
    audio = FakeAudio()
    persistence = FakePersistence(known_words={"我们", "学习"})
    processor = FakeChineseProcessor()

    result = process_video(
        transcript_source=transcript,
        audio_processor=audio,
        persistence=persistence,
        language_processor=processor,
        video_id="test789",
        output_dir="/tmp/test",
        max_cards=10,
    )

    assert len(result["i1_candidates"]) == 10


def test_process_video_returns_summary():
    """process_video should return a summary dict with counts."""
    transcript = FakeTranscript(["我们 一般 学习", "我 爱 你", "今天 天气 很好"])
    audio = FakeAudio()
    persistence = FakePersistence(known_words={"我们", "学习", "我", "爱", "你"})
    processor = FakeChineseProcessor()

    result = process_video(
        transcript_source=transcript,
        audio_processor=audio,
        persistence=persistence,
        language_processor=processor,
        video_id="test000",
        output_dir="/tmp/test",
    )

    assert "i1_candidates" in result
    assert "i0_count" in result
    assert "stash_count" in result
    assert "total_sentences" in result

    assert result["i0_count"] == 1
    assert result["stash_count"] == 1
    assert result["total_sentences"] == 3
