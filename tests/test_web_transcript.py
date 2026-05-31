"""Tests for the GET /api/videos/<id>/transcript endpoint."""

import json
import pytest

from langmine.domain.ports import (
    LanguageProcessor, Persistence, TranscriptSource, AudioProcessor,
    TranscriptChunk,
)
from langmine.domain.models import Video, Sentence, VocabWord


# === Fake ports (minimal replicas of test_web_api.py fakes) ===

class FakeLanguageProcessor(LanguageProcessor):
    def segment(self, text): return text.split()
    def get_reading(self, text): return " ".join(f"py:{t}" for t in text.split())
    def lookup_word(self, word): return {"definition_de": f"def:{word}", "definition_en": f"def:{word}"}
    def translate_sentence(self, text): return f"[DE] {text}"
    def get_frequency(self, word):
        ranks = {"一般": 1847, "效率": 3412, "爬山": 5000}
        return ranks.get(word)
    def is_non_word(self, token): return token in {"的", "了", "吗", "啊", "呢", "吧"}
    def find_known_synonyms(self, word, known_words): return []
    def get_annotation(self, text): return "[]"


class FakePersistence(Persistence):
    def __init__(self, known_words=None):
        self._known = known_words or set()
        self._videos = []
        self._sentences = []
        self._vocab = []
        self._next_vid = 1
        self._next_sid = 1

    def save_video(self, video):
        if video.id is None:
            video.id = self._next_vid; self._next_vid += 1; self._videos.append(video)

    def get_video(self, yt_id):
        for v in self._videos:
            if v.youtube_id == yt_id: return v
        return None

    def list_videos(self, language_code: str = ""): return list(self._videos)
    def video_exists(self, yt_id): return any(v.youtube_id == yt_id for v in self._videos)

    def save_sentences(self, sentences):
        for s in sentences:
            if s.id is None:
                s.id = self._next_sid; self._next_sid += 1
            self._sentences.append(s)

    def get_sentences_by_video(self, vid, status=None, language_code: str = ""):
        results = [s for s in self._sentences if s.video_id == vid]
        if status: results = [s for s in results if s.status == status]
        return results

    def update_sentence(self, s):
        for i, existing in enumerate(self._sentences):
            if existing.id == s.id: self._sentences[i] = s; break

    def get_known_words(self, language_code: str = ""):
        return self._known | {w.word_simplified for w in self._vocab if w.status in ("known", "ignored")}

    def get_vocab_word(self, w):
        for v in self._vocab:
            if v.word_simplified == w: return v
        return None

    def save_vocab_word(self, w): self._vocab.append(w)
    def mark_word_known(self, w):
        existing = self.get_vocab_word(w)
        if existing: existing.status = "known"
        else: self._vocab.append(VocabWord(word_simplified=w, status="known"))
    def mark_word_learning(self, w):
        existing = self.get_vocab_word(w)
        if existing: existing.status = "learning"
        else: self._vocab.append(VocabWord(word_simplified=w, status="learning"))
    def get_vocab_stats(self, language_code: str = ""): return {"known": 0, "learning": 0, "total": len(self._vocab)}
    def list_vocab(self, page=1, per_page=200, status=None, search=None, sort="frequency", language_code: str = ""):
        return [], 0

    def mark_word_ignored(self, word_simplified: str) -> None:
        existing = self.get_vocab_word(word_simplified)
        if existing:
            existing.status = "ignored"
        else:
            self._vocab.append(VocabWord(word_simplified=word_simplified, status="ignored"))

        words = list(self._vocab)
        if status: words = [w for w in words if w.status == status]
        if search: words = [w for w in words if search.lower() in w.word_simplified.lower()]
        words.sort(key=lambda w: (w.frequency_rank is None, w.frequency_rank or 999999))
        return words[:per_page], len(words)
    def get_sentences_by_word(self, word):
        return [s for s in self._sentences if s.unknown_word == word or word in s.text]

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

    def get_stash_candidates(self, limit=20):
        return [s for s in self._sentences if s.status == "stashed"][:limit]
    def get_sentences_by_status(self, status, language_code: str = ""):
        return [s for s in self._sentences if s.status == status]
    def reclassify_stashed(self, vid): return 0


class FakeTranscriptSource(TranscriptSource):
    def fetch(self, video_id):
        return [TranscriptChunk(text="你好", start_ms=0, duration_ms=500)]


class FakeAudioProcessor(AudioProcessor):
    def download(self, video_id, output_dir): return f"{output_dir}/{video_id}.mp3"
    def clip(self, *args, **kwargs): return "/tmp/clip.mp3"
    def capture_frame(self, video_id, timestamp_ms, output_dir, sentence_id):
        return f"{output_dir}/frame_{sentence_id}.jpg"


# === Fixtures ===

@pytest.fixture
def persistence():
    return FakePersistence(known_words={"我们", "早上", "起床", "学习", "我", "爱", "你"})


@pytest.fixture
def processor():
    return FakeLanguageProcessor()


@pytest.fixture
def transcript():
    return FakeTranscriptSource()


@pytest.fixture
def audio():
    return FakeAudioProcessor()


@pytest.fixture
def client(persistence, processor, transcript, audio):
    from langmine.web.app import create_app
    app = create_app(
        persistence=persistence,
        language_processor=processor,
        transcript_source=transcript,
        audio_processor=audio,
    )
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture
def client_with_ordered_sentences(client, persistence):
    """Test client with sentences inserted out of time-order to verify sorting."""
    video = Video(youtube_id="dQw4w9WgXcQ", title="Test Video", channel="Test Channel")
    persistence.save_video(video)

    sentences = [
        Sentence(
            video_id=video.id, start_ms=8000, end_ms=12000,
            text="我们 需要 提高 效率", text_segmented="我们 / 需要 / 提高 / 效率",
            reading="wǒmen xūyào tígāo xiàolǜ",
            translation_de="Wir müssen Effizienz verbessern",
            unknown_word="效率", unknown_word_rank=3412,
            status="i1",
        ),
        Sentence(
            video_id=video.id, start_ms=1000, end_ms=3000,
            text="我们 一般 早上 起床", text_segmented="我们 / 一般 / 早上 / 起床",
            reading="wǒmen yībān zǎoshang qǐchuáng",
            translation_de="Wir stehen normalerweise morgens auf",
            unknown_word="一般", unknown_word_rank=1847,
            audio_clip_path="/tmp/clip1.mp3",
            status="i1",
        ),
        Sentence(
            video_id=video.id, start_ms=4000, end_ms=7000,
            text="我 爱 学习", text_segmented="我 / 爱 / 学习",
            reading="wǒ ài xuéxí",
            translation_de="Ich liebe es zu lernen",
            status="i0",
        ),
    ]
    for s in sentences:
        persistence.save_sentences([s])

    return client, persistence


# === Tests ===

class TestTranscriptEndpoint:
    """GET /api/videos/<video_id>/transcript"""

    def test_returns_200_with_sentences(self, client_with_ordered_sentences):
        client, _ = client_with_ordered_sentences
        resp = client.get("/api/videos/1/transcript")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["video_id"] == 1
        assert len(data["sentences"]) == 3

    def test_sentences_sorted_by_start_ms(self, client_with_ordered_sentences):
        client, _ = client_with_ordered_sentences
        resp = client.get("/api/videos/1/transcript")
        data = json.loads(resp.data)
        starts = [s["start_ms"] for s in data["sentences"]]
        assert starts == sorted(starts), f"Expected sorted starts, got {starts}"
        assert data["sentences"][0]["start_ms"] == 1000

    def test_nonexistent_video_returns_empty(self, client):
        resp = client.get("/api/videos/999/transcript")
        data = json.loads(resp.data)
        assert data["sentences"] == []

    def test_sentence_has_required_fields(self, client_with_ordered_sentences):
        client, _ = client_with_ordered_sentences
        resp = client.get("/api/videos/1/transcript")
        data = json.loads(resp.data)
        s = data["sentences"][0]
        required = ["id", "video_id", "text", "text_segmented", "reading",
                     "translation_de", "unknown_word", "start_ms", "end_ms",
                     "status", "has_audio", "has_screenshot"]
        for field in required:
            assert field in s, f"Missing field: {field}"

    def test_sentence_includes_words_array(self, client_with_ordered_sentences):
        client, _ = client_with_ordered_sentences
        resp = client.get("/api/videos/1/transcript")
        data = json.loads(resp.data)
        for sentence in data["sentences"]:
            assert "words" in sentence, "Transcript sentences must include words array"
            assert isinstance(sentence["words"], list)
            if sentence["words"]:
                w = sentence["words"][0]
                assert "token" in w
                assert "status" in w

    def test_all_statuses_included(self, client_with_ordered_sentences):
        """Transcript includes deleted sentences (full context)."""
        client, persistence = client_with_ordered_sentences
        sentences = persistence.get_sentences_by_video(1)
        for s in sentences:
            if s.status == "i0":
                s.status = "deleted"
                persistence.update_sentence(s)
                break

        resp = client.get("/api/videos/1/transcript")
        data = json.loads(resp.data)
        statuses = {s["status"] for s in data["sentences"]}
        assert "deleted" in statuses, "Transcript should include deleted sentences"
        assert len(data["sentences"]) == 3
