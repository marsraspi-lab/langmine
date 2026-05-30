"""Tests for M13 difficulty preview endpoint (POST /api/videos/preview)."""

import json
import pytest

from langmine.domain.ports import (
    LanguageProcessor, Persistence, TranscriptSource, AudioProcessor,
    TranscriptChunk,
)
from langmine.domain.models import VocabWord


# === Fake Ports ===

class FakeLanguageProcessor(LanguageProcessor):
    def segment(self, text):
        return text.split()

    def get_reading(self, text):
        return " ".join(f"py:{t}" for t in text.split())

    def lookup_word(self, word):
        return {"definition_de": f"def:{word}", "definition_en": f"def:{word}"}

    def translate_sentence(self, text):
        return f"[DE] {text}"

    def get_frequency(self, word):
        return 1000

    def is_non_word(self, token):
        return token in {"的", "了", "吗", "啊", "呢", "吧", "很", "是", "和", "不"}

    def find_known_synonyms(self, word, known_words): return []
    def get_ruby(self, text): return "[]"


class FakePersistence(Persistence):
    def __init__(self, known_words=None):
        self._known = known_words or set()
        self._videos = []
        self._sentences = []
        self._vocab = []
        self._next_vid = 1
        self._next_sid = 1

    def get_known_words(self):
        return self._known

    # Stubs for unused methods
    def save_video(self, v):
        if v.id is None:
            v.id = self._next_vid; self._next_vid += 1; self._videos.append(v)

    def list_videos(self):
        return list(self._videos)

    def get_video(self, yt_id):
        for v in self._videos:
            if v.youtube_id == yt_id:
                return v
        return None

    def video_exists(self, yt_id):
        return any(v.youtube_id == yt_id for v in self._videos)

    def save_sentences(self, sentences):
        for s in sentences:
            if s.id is None:
                s.id = self._next_sid; self._next_sid += 1
            self._sentences.append(s)

    def get_sentences_by_video(self, vid, status=None):
        results = [s for s in self._sentences if s.video_id == vid]
        if status:
            results = [s for s in results if s.status == status]
        return results

    def update_sentence(self, s):
        for i, existing in enumerate(self._sentences):
            if existing.id == s.id:
                self._sentences[i] = s; break

    def get_vocab_word(self, w):
        for v in self._vocab:
            if v.word_simplified == w:
                return v
        return None

    def save_vocab_word(self, w):
        self._vocab.append(w)

    def mark_word_known(self, w):
        existing = self.get_vocab_word(w)
        if existing:
            existing.status = "known"
        else:
            self._vocab.append(VocabWord(word_simplified=w, status="known"))

    def mark_word_learning(self, w):
        existing = self.get_vocab_word(w)
        if existing:
            existing.status = "learning"
        else:
            self._vocab.append(VocabWord(word_simplified=w, status="learning"))

    def get_vocab_stats(self):
        return {"known": 0, "learning": 0, "total": 0}

    def list_vocab(self, page=1, per_page=200, status=None, search=None, sort="frequency"):
        return [], 0

    def get_sentences_by_word(self, word):
        return []

    def get_stash_candidates(self, limit=20):
        return []

    def get_sentences_by_status(self, status):
        return []

    def reclassify_stashed(self, vid):
        return 0


class FakeTranscriptSource(TranscriptSource):
    def __init__(self, chunks=None):
        self._chunks = chunks or [TranscriptChunk(text="test", start_ms=0, duration_ms=500)]

    def fetch(self, video_id):
        return self._chunks


class FakeAudioProcessor(AudioProcessor):
    def download(self, video_id, output_dir):
        return "/tmp/test.mp3"

    def clip(self, audio_path, start_ms, end_ms, pad_before_ms, pad_after_ms, output_dir, sentence_id):
        return f"{output_dir}/{sentence_id}.mp3"

    def capture_frame(self, video_id, timestamp_ms, output_dir, sentence_id):
        return None


# === Transcript chunks that produce 3 sentences ===
#
# Chunks with >500ms gaps produce separate sentences via merge_sentences():
#   Chunk 0: start=0, dur=500  → ends at 500
#   Chunk 1: start=1500, dur=500  → gap=1000 > 500 → new sentence. ends at 2000
#   Chunk 2: start=3000, dur=500  → gap=1000 > 500 → new sentence. ends at 3500
#
# Sentence 1: "我们 早上 起床" → all known → i0
# Sentence 2: "我 爱 爬山"     → 爬山 unknown → i1
# Sentence 3: "一般 效率 很 高" → 很 is non-word, 一般+效率 unknown → stash

PREVIEW_CHUNKS = [
    TranscriptChunk(text="我们 早上 起床", start_ms=0, duration_ms=500),
    TranscriptChunk(text="我 爱 爬山", start_ms=1500, duration_ms=500),
    TranscriptChunk(text="一般 效率 很 高", start_ms=3000, duration_ms=500),
]


# === Fixtures ===

@pytest.fixture
def processor():
    return FakeLanguageProcessor()


@pytest.fixture
def persistence():
    known = {"我们", "早上", "起床", "学习", "我", "爱", "你", "高"}
    return FakePersistence(known_words=known)


@pytest.fixture
def transcript():
    return FakeTranscriptSource(chunks=PREVIEW_CHUNKS)


@pytest.fixture
def audio():
    return FakeAudioProcessor()


@pytest.fixture
def client(processor, persistence, transcript, audio):
    from langmine.web.app import create_app
    app = create_app(
        persistence=persistence,
        language_processor=processor,
        transcript_source=transcript,
        audio_processor=audio,
    )
    app.config["TESTING"] = True
    return app.test_client()


# === Tests ===

class TestDifficultyPreview:
    """POST /api/videos/preview — difficulty assessment before mining."""

    def test_preview_returns_stats(self, client):
        """Returns total_sentences, i1_estimated, i0_count, and percentage stats."""
        resp = client.post("/api/videos/preview", json={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        })
        assert resp.status_code == 200
        data = json.loads(resp.data)

        assert data["total_sentences"] == 3
        assert data["i1_estimated"] == 1   # "我 爱 爬山" — only 爬山 unknown
        assert data["i0_count"] == 1        # "我们 早上 起床" — all known
        # stash: "一般 效率 很 高" — 很 non-word, 一般+效率 unknown → 2 unknowns
        assert data["stash_count"] == 1
        assert "known_word_pct" in data
        assert "avg_unknown_per_sentence" in data
        assert len(data["sentences"]) == 3

    def test_preview_sentences_have_word_status(self, client):
        """Each sentence.words[] has per-token status for highlighting."""
        resp = client.post("/api/videos/preview", json={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        })
        data = json.loads(resp.data)

        # Sentence 1: "我们 早上 起床" — all known
        s1 = data["sentences"][0]
        assert [w["status"] for w in s1["words"]] == ["known", "known", "known"]

        # Sentence 2: "我 爱 爬山" — 爬山 is unknown (not in known set)
        s2 = data["sentences"][1]
        s2_statuses = [w["status"] for w in s2["words"]]
        assert "learning" in s2_statuses  # 爬山

        # Sentence 3: "一般 效率 很 高" — 很 is non-word
        s3 = data["sentences"][2]
        s3_statuses = [w["status"] for w in s3["words"]]
        assert "non-word" in s3_statuses  # 很

    def test_preview_includes_segmented_pinyin_translation(self, client):
        """Preview sentences include text_segmented, pinyin, and translation_de."""
        resp = client.post("/api/videos/preview", json={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        })
        data = json.loads(resp.data)
        s = data["sentences"][0]

        assert " / " in s["text_segmented"]
        assert s["pinyin"].startswith("py:")
        assert s["translation_de"].startswith("[DE]")
        assert "start_ms" in s
        assert "end_ms" in s
        assert "unknown_count" in s

    def test_preview_rejects_missing_url(self, client):
        """Missing 'url' field returns 400."""
        resp = client.post("/api/videos/preview", json={})
        assert resp.status_code == 400

    def test_preview_handles_unavailable_video(self, persistence, processor, audio):
        """Transcript source raising ValueError returns 400."""
        from langmine.web.app import create_app

        class FailingTranscriptSource(TranscriptSource):
            def fetch(self, video_id):
                raise ValueError("No transcript available for video 'test'.")

        app = create_app(
            persistence=persistence,
            language_processor=processor,
            transcript_source=FailingTranscriptSource(),
            audio_processor=audio,
        )
        app.config["TESTING"] = True
        client = app.test_client()

        resp = client.post("/api/videos/preview", json={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        })
        assert resp.status_code == 400
        data = json.loads(resp.data)
        assert "error" in data

    def test_preview_no_persistence_side_effects(self, client, persistence):
        """Preview does not persist any videos or sentences."""
        initial_video_count = len(persistence.list_videos())
        initial_sentence_count = len(persistence._sentences)

        client.post("/api/videos/preview", json={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        })

        assert len(persistence.list_videos()) == initial_video_count
        assert len(persistence._sentences) == initial_sentence_count

    def test_preview_known_word_pct_is_accurate(self, client):
        """known_word_pct reflects the ratio of known content words."""
        resp = client.post("/api/videos/preview", json={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        })
        data = json.loads(resp.data)

        # Known content words: 我们, 早上, 起床, 我, 爱, 高 = 6
        # Unknown content words: 爬山, 一般, 效率 = 3
        # Non-words (excluded): 很 = 1
        # Total content words = 9, known = 6 → 6/9 = 66.7%
        assert data["known_word_pct"] == pytest.approx(66.7, abs=0.1)
