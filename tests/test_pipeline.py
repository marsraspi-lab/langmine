"""Tests for process_video() — full video mining with classification."""

import json

import pytest

from langmine.config import Config
from langmine.domain.models import Sentence, VocabWord
from langmine.domain.ports import (
    AudioProcessor,
    LanguageProcessor,
    Persistence,
    TranscriptSource,
)
from langmine.pipeline import process_video

_TEST_CONFIG = Config()

# === Fake ports with Chinese NLP ===


class FakeChineseProcessor(LanguageProcessor):
    """Returns predictable Chinese segmentation and frequency."""

    def __init__(self):
        self.bootstrap_calls = []

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

    def is_proper_name(self, token: str) -> bool:
        return False

    def find_known_synonyms(self, word: str, known_words: set[str]) -> list[str]:
        return []

    def get_annotation(self, text: str) -> str:
        return "[]"

    def bootstrap_proficiency(self, persistence, settings, language_code):
        self.bootstrap_calls.append((settings, language_code))


class FakeTranscript(TranscriptSource):
    def __init__(self, chunks, fail_on_fetch=False):
        from langmine.domain.ports import TranscriptChunk

        # Spread chunks apart so they don't merge (1000ms gap between sentences)
        self.chunks = [
            TranscriptChunk(text=t, start_ms=i * 2000, duration_ms=1000)
            for i, t in enumerate(chunks)
        ]
        self.fail_on_fetch = fail_on_fetch

    def fetch(self, video_id: str, language: str = ""):
        if self.fail_on_fetch:
            raise RuntimeError("Fetch failed")
        return self.chunks

    def list_subtitles(self, video_id: str):
        return []


class FakeAudio(AudioProcessor):
    def __init__(self):
        self.captured_frames = []
        self.clips = []
        self.downloads = []

    def download(self, video_id: str, output_dir: str) -> str:
        self.downloads.append((video_id, output_dir))
        return f"{output_dir}/{video_id}.mp3"

    def clip(
        self,
        audio_path,
        start_ms,
        end_ms,
        pad_before_ms,
        pad_after_ms,
        output_dir,
        sentence_id,
    ):
        self.clips.append((start_ms, end_ms, sentence_id))
        return f"{output_dir}/sentence_{sentence_id}.mp3"

    def capture_frame(self, video_id, timestamp_ms, output_dir, sentence_id):
        self.captured_frames.append((video_id, timestamp_ms))
        return f"{output_dir}/frame_{sentence_id}.jpg"


class FakePersistence(Persistence):
    def __init__(self, known_words: set[str] | None = None):
        self._known = known_words or set()
        self._ignored = set()
        self.videos: dict = {}
        self.sentences: list[Sentence] = []
        self._vocab: list[VocabWord] = []
        self.events = []

    def get_known_words(self) -> set[str]:
        return (
            self._known
            | self._ignored
            | {
                w.word_simplified
                for w in self._vocab
                if w.status in ("known", "ignored")
            }
        )

    def save_video(self, video):
        if video.id is None:
            video.id = len(self.videos) + 1
        self.videos[video.youtube_id] = video

    def get_video(self, yt_id):
        return self.videos.get(yt_id)

    def list_videos(self):
        return list(self.videos.values())

    def delete_video(self, video_id: int) -> bool:
        return False  # not found in fake

    def save_sentences(self, sentences):
        for s in sentences:
            s.id = len(self.sentences) + 1
            self.sentences.append(s)

    def get_sentences_by_video(self, vid, status=None):
        result = [s for s in self.sentences if s.video_id == vid]
        if status:
            result = [s for s in result if s.status == status]
        return result

    def update_sentence(self, s):
        pass

    def get_sentences_by_status(self, status):
        return []

    def save_vocab_word(self, w: VocabWord) -> None:
        self._vocab.append(w)

    def get_vocab_word(self, word_simplified: str) -> VocabWord | None:
        for w in self._vocab:
            if w.word_simplified == word_simplified:
                return w
        return None

    def mark_word_known(self, w):
        pass

    def mark_word_learning(self, w):
        pass

    def get_vocab_stats(self):
        return {"known": 0, "learning": 0, "total": 0}

    def list_vocab(
        self, page=1, per_page=200, status=None, search=None, sort="frequency"
    ):
        return [], 0

    def get_sentences_by_word(self, word):
        return [s for s in self.sentences if s.unknown_word == word or word in s.text]

    def mark_word_ignored(self, word_simplified: str) -> None:
        self._ignored.add(word_simplified)

    def log_event(
        self,
        entity_type: str,
        entity_id: int,
        action: str,
        old_value: str = "",
        new_value: str = "",
        language_code: str = "",
    ) -> None:
        self.events.append(
            {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "action": action,
                "new_value": new_value,
                "language_code": language_code,
            }
        )


# === Tests ===


def test_process_video_saves_video():
    """process_video should save the video in persistence."""
    transcript = FakeTranscript(["你好世界", "我很好"])
    audio = FakeAudio()
    persistence = FakePersistence(known_words={"我", "很好", "你", "好", "世界"})
    processor = FakeChineseProcessor()

    process_video(
        transcript_source=transcript,
        audio_processor=audio,
        persistence=persistence,
        language_processor=processor,
        video_id="test123",
        output_dir="/tmp/test",
        config=_TEST_CONFIG,
    )

    assert persistence.get_video("test123") is not None
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
        config=_TEST_CONFIG,
    )

    # "我们 一般 学习" — "一般" unknown → i1
    i1 = result["i1_candidates"]
    assert len(i1) == 1
    assert i1[0].unknown_word == "一般"

    # "我 爱 你" — all known → i0
    i0_count = result["i0_count"]
    assert i0_count == 1


def test_process_video_applies_cap():
    """process_video should respect max_cards from config for i+1 candidates."""
    # Create 25 sentences each with one unique unknown word
    texts = [f"我们 word{i} 学习" for i in range(25)]
    transcript = FakeTranscript(texts)
    audio = FakeAudio()
    persistence = FakePersistence(known_words={"我们", "学习"})
    processor = FakeChineseProcessor()

    capped_config = Config()
    capped_config.max_cards_per_video = 10
    result = process_video(
        transcript_source=transcript,
        audio_processor=audio,
        persistence=persistence,
        language_processor=processor,
        video_id="test789",
        output_dir="/tmp/test",
        config=capped_config,
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
        config=_TEST_CONFIG,
    )

    assert "i1_candidates" in result
    assert "i0_count" in result
    assert "stash_count" in result
    assert "total_sentences" in result

    assert result["i0_count"] == 1
    assert result["stash_count"] == 1
    assert result["total_sentences"] == 3


def test_process_video_passes_subtitle_language_to_fetch():
    """subtitle_language should be passed to transcript_source.fetch()."""
    transcript = FakeTranscript(["我们 学习"])
    audio = FakeAudio()
    persistence = FakePersistence(known_words={"我们", "学习"})
    processor = FakeChineseProcessor()

    # Wrap fetch to capture the language argument
    original_fetch = transcript.fetch
    captured_language = []

    def tracking_fetch(video_id, language=""):
        captured_language.append(language)
        return original_fetch(video_id, language=language)

    transcript.fetch = tracking_fetch

    process_video(
        transcript_source=transcript,
        audio_processor=audio,
        persistence=persistence,
        language_processor=processor,
        video_id="test_lang",
        output_dir="/tmp/test",
        subtitle_language="zh-Hans",
        config=_TEST_CONFIG,
    )

    assert captured_language == ["zh-Hans"], (
        f"Expected fetch(language='zh-Hans') but got {captured_language}"
    )


def test_process_video_bootstraps_proficiency():
    """process_video should call bootstrap_proficiency with config values."""
    transcript = FakeTranscript(["你好"])
    audio = FakeAudio()
    persistence = FakePersistence()
    processor = FakeChineseProcessor()

    from langmine.config import Config

    boot_config = Config()
    boot_config.language_settings = {"zh": {"bootstrap_level": 3}}
    boot_config.source_language = "zh"
    process_video(
        transcript_source=transcript,
        audio_processor=audio,
        persistence=persistence,
        language_processor=processor,
        video_id="test_boot",
        output_dir="/tmp/test",
        config=boot_config,
    )

    assert processor.bootstrap_calls == [({"bootstrap_level": 3}, "zh")]


def test_process_video_skips_i0_screenshots():
    """Screenshots should only be captured for i1 or stashed sentences."""
    transcript = FakeTranscript(["已知", "未知"])
    audio = FakeAudio()
    persistence = FakePersistence(known_words={"已知"})
    processor = FakeChineseProcessor()

    process_video(
        transcript_source=transcript,
        audio_processor=audio,
        persistence=persistence,
        language_processor=processor,
        video_id="test_snap",
        output_dir="/tmp/test",
        config=_TEST_CONFIG,
    )

    # Only one frame should be captured (for "未知")
    # "已知" is i0, so it's skipped
    assert len(audio.captured_frames) == 1
    # Check that it's the second sentence (timestamp_ms=2000)
    assert audio.captured_frames[0][1] == 2000


def test_process_video_logs_events():
    """process_video should log classification events for each sentence."""
    transcript = FakeTranscript(["已知", "未知"])
    audio = FakeAudio()
    persistence = FakePersistence(known_words={"已知"})
    processor = FakeChineseProcessor()

    process_video(
        transcript_source=transcript,
        audio_processor=audio,
        persistence=persistence,
        language_processor=processor,
        video_id="test_events",
        output_dir="/tmp/test",
        config=_TEST_CONFIG,
    )

    # 2 sentences -> 2 events
    assert len(persistence.events) == 2
    actions = [e["action"] for e in persistence.events]
    assert "classified_i0" in actions
    assert "classified_i1" in actions


def test_process_video_handles_stage_errors():
    """MineError should be raised with the correct stage if a step fails."""
    from langmine.pipeline import MineError

    transcript = FakeTranscript([], fail_on_fetch=True)
    audio = FakeAudio()
    persistence = FakePersistence()
    processor = FakeChineseProcessor()

    with pytest.raises(MineError) as excinfo:
        process_video(
            transcript_source=transcript,
            audio_processor=audio,
            persistence=persistence,
            language_processor=processor,
            video_id="test_err",
            output_dir="/tmp/test",
            config=_TEST_CONFIG,
        )

    assert excinfo.value.stage == "transcript"
    assert "Fetch failed" in str(excinfo.value)


def test_process_video_downloads_audio_and_clips_sentences():
    """process_video should download full audio, then clip each sentence."""
    transcript = FakeTranscript(["已知", "未知 单词"])
    audio = FakeAudio()
    persistence = FakePersistence(known_words={"已知"})
    processor = FakeChineseProcessor()

    process_video(
        transcript_source=transcript,
        audio_processor=audio,
        persistence=persistence,
        language_processor=processor,
        video_id="test_audio",
        output_dir="/tmp/test",
        config=_TEST_CONFIG,
    )

    # Audio should be downloaded once for the video
    assert len(audio.downloads) == 1
    assert audio.downloads[0][0] == "test_audio"

    # All sentences should get audio clips (not just i1)
    assert len(audio.clips) == 2

    # All persisted sentences should have audio_clip_path set
    for s in persistence.sentences:
        assert s.audio_clip_path, f"Sentence {s.id} ({s.text}) missing audio_clip_path"

    # Verify clips match sentence timing
    assert audio.clips[0][0:2] == (0, 1000)  # first sentence start/end ms
    assert audio.clips[1][0:2] == (2000, 3000)  # second sentence start/end ms


def test_process_video_caches_transcript_json():
    """process_video should store raw transcript chunks as JSON on the video."""
    transcript = FakeTranscript(["已知", "未知 单词"])
    audio = FakeAudio()
    persistence = FakePersistence(known_words={"已知"})
    processor = FakeChineseProcessor()

    process_video(
        transcript_source=transcript,
        audio_processor=audio,
        persistence=persistence,
        language_processor=processor,
        video_id="test_cache",
        output_dir="/tmp/test",
        config=_TEST_CONFIG,
    )

    video = persistence.get_video("test_cache")
    assert video.transcript_json, "transcript_json should not be empty"

    chunks = json.loads(video.transcript_json)
    assert len(chunks) == 2
    assert chunks[0]["text"] == "已知"
    assert chunks[0]["start_ms"] == 0
    assert chunks[1]["text"] == "未知 单词"
    assert chunks[1]["start_ms"] == 2000
