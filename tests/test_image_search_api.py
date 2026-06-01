"""Tests for M12 image search API endpoints."""

import json
import pytest

from langmine.domain.models import Video, Sentence, VocabWord
from langmine.domain.ports import (
    LanguageProcessor, Persistence, TranscriptSource, AudioProcessor,
    TranscriptChunk,
)


# === Fake ports ===

class FakeLanguageProcessor(LanguageProcessor):
    def segment(self, text): return text.split()
    def get_reading(self, text): return " ".join(f"py:{t}" for t in text.split())
    def lookup_word(self, word): return {"definition_de": f"def:{word}", "definition_en": f"def:{word}"}
    def translate_sentence(self, text): return f"[DE] {text}"
    def get_frequency(self, word): return 1000
    def is_non_word(self, token): return token in {"的", "了", "吗", "啊", "呢", "吧"}
    def is_proper_name(self, token, context_sentence=""): return False
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
        if video.id is None: video.id = self._next_vid; self._next_vid += 1; self._videos.append(video)
    def get_video(self, yt_id):
        for v in self._videos:
            if v.youtube_id == yt_id: return v
        return None
    def list_videos(self, language_code: str = ""): return list(self._videos)
    def video_exists(self, yt_id): return any(v.youtube_id == yt_id for v in self._videos)
    def delete_video(self, video_id: int) -> bool:
        return False  # not found in fake
    def save_sentences(self, sentences):
        for s in sentences:
            if s.id is None: s.id = self._next_sid; self._next_sid += 1
            self._sentences.append(s)
    def get_sentences_by_video(self, vid, status=None):
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
    def get_vocab_stats(self, language_code: str = ""): return {"known": 0, "learning": 0, "total": 0}
    def list_vocab(self, page=1, per_page=200, status=None, search=None, sort="frequency", language_code: str = ""):
        return [], 0

    def mark_word_ignored(self, word_simplified: str) -> None:
        existing = self.get_vocab_word(word_simplified)
        if existing:
            existing.status = "ignored"
        else:
            self._vocab.append(VocabWord(word_simplified=word_simplified, status="ignored"))
    def get_sentences_by_word(self, word): return []

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

    def get_stash_candidates(self, limit=20): return []
    def get_sentences_by_status(self, status, language_code: str = ""): return []
    def reclassify_stashed(self, vid): return 0


class FakeTranscriptSource(TranscriptSource):
    def fetch(self, video_id):
        return [TranscriptChunk(text="test", start_ms=0, duration_ms=500)]

    def list_subtitles(self, video_id):
        return []


class FakeAudioProcessor(AudioProcessor):
    def download(self, video_id, output_dir): return f"{output_dir}/{video_id}.mp3"
    def clip(self, *args, **kwargs): return "/tmp/clip.mp3"
    def capture_frame(self, video_id, timestamp_ms, output_dir, sentence_id):
        return f"{output_dir}/frame_{sentence_id}.jpg"


# === Fixtures ===

@pytest.fixture
def persistence():
    return FakePersistence()


@pytest.fixture
def client(persistence):
    from langmine.web.app import create_app
    app = create_app(
        persistence=persistence,
        language_processor=FakeLanguageProcessor(),
        transcript_source=FakeTranscriptSource(),
        audio_processor=FakeAudioProcessor(),
    )
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture
def client_with_sentences(client, persistence):
    video = Video(youtube_id="dQw4w9WgXcQ", title="Test", channel="C")
    persistence.save_video(video)
    sentences = [
        Sentence(video_id=video.id, start_ms=1000, end_ms=3000,
                 text="我们 一般 早上 起床", text_segmented="我们 / 一般 / 早上 / 起床",
                 status="i1"),
    ]
    persistence.save_sentences(sentences)
    return client, persistence


# === Tests ===

class TestSentenceClozeImage:
    """M12: Sentence model has cloze_image_url field."""

    def test_sentence_has_cloze_image_url(self):
        s = Sentence(
            video_id=1, start_ms=0, end_ms=1000,
            text="test", text_segmented="test",
            cloze_image_url="https://example.com/img.jpg",
        )
        assert s.cloze_image_url == "https://example.com/img.jpg"

    def test_cloze_image_url_defaults_to_none(self):
        s = Sentence(
            video_id=1, start_ms=0, end_ms=1000,
            text="test", text_segmented="test",
        )
        assert s.cloze_image_url is None


class TestImageSearchAPI:
    """M12: GET /api/images/search and POST /api/sentences/:id/cloze-image."""

    @pytest.fixture
    def client_with_searcher(self, persistence):
        from unittest.mock import MagicMock
        from langmine.web.app import create_app

        fake_searcher = MagicMock()
        fake_searcher.search.return_value = [
            "https://example.com/img1.jpg",
            "https://example.com/img2.jpg",
        ]

        app = create_app(
            persistence=persistence,
            language_processor=FakeLanguageProcessor(),
            transcript_source=FakeTranscriptSource(),
            audio_processor=FakeAudioProcessor(),
            image_searcher=fake_searcher,
        )
        app.config["TESTING"] = True
        return app.test_client(), persistence, fake_searcher

    def test_image_search_returns_urls(self, client_with_searcher):
        client, _, fake_searcher = client_with_searcher
        resp = client.get("/api/images/search?q=%E8%8B%B9%E6%9E%9C&count=2")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "images" in data
        assert len(data["images"]) == 2
        assert data["images"][0].startswith("https://")
        fake_searcher.search.assert_called_once_with("苹果", count=2)

    def test_image_search_missing_query(self, client_with_searcher):
        client, _, _ = client_with_searcher
        resp = client.get("/api/images/search")
        assert resp.status_code == 400

    def test_image_search_no_searcher_configured(self, client):
        resp = client.get("/api/images/search?q=test")
        assert resp.status_code == 503

    def test_set_cloze_image(self, client_with_sentences):
        client, persistence = client_with_sentences
        resp = client.post(
            "/api/sentences/1/cloze-image",
            data=json.dumps({"image_url": "https://example.com/chosen.jpg"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["ok"] is True
        assert data["cloze_image_url"] == "https://example.com/chosen.jpg"
        sentences = persistence.get_sentences_by_video(1)
        s = [s for s in sentences if s.id == 1][0]
        assert s.cloze_image_url == "https://example.com/chosen.jpg"

    def test_set_cloze_image_not_found(self, client):
        resp = client.post(
            "/api/sentences/999/cloze-image",
            data=json.dumps({"image_url": "https://example.com/img.jpg"}),
            content_type="application/json",
        )
        assert resp.status_code == 404
