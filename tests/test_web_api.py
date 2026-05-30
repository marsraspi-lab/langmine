"""Tests for the LangMine Flask web API.

Tested against FakePersistence and FakeLanguageProcessor.
No YouTube, ffmpeg, SQLite, or network required.
"""

import json
import pytest
from pathlib import Path

from langmine.domain.ports import (
    LanguageProcessor, Persistence, Dictionary, Translator,
    FrequencySource, MergedSentence, TranscriptSource, AudioProcessor,
    TranscriptChunk,
)
from langmine.domain.models import Video, Sentence, VocabWord


# === Fake Ports (same pattern as test_classifier.py) ===


class FakeLanguageProcessor(LanguageProcessor):
    """Returns predictable NLP output."""

    def __init__(self, known_words: set[str] | None = None):
        self._known_words = known_words or set()

    def segment(self, text: str) -> list[str]:
        return text.split()

    def get_reading(self, text: str) -> str:
        return " ".join(f"py:{t}" for t in text.split())

    def lookup_word(self, word: str) -> dict | None:
        return {"definition_de": f"def_de:{word}", "definition_en": f"def_en:{word}"}

    def translate_sentence(self, text: str) -> str:
        return f"[DE] {text}"

    def get_frequency(self, word: str) -> int | None:
        ranks = {"一般": 1847, "效率": 3412, "爬山": 5000}
        return ranks.get(word)

    def is_non_word(self, token: str) -> bool:
        return token in {"的", "了", "吗", "啊", "呢", "吧"}

    def find_known_synonyms(self, word, known_words): return []
    def get_ruby(self, text): return "[]"


class FakePersistence(Persistence):
    """In-memory persistence for testing."""

    def __init__(self, known_words: set[str] | None = None):
        self._known = known_words or set()
        self._videos: list[Video] = []
        self._sentences: list[Sentence] = []
        self._next_video_id = 1
        self._next_sentence_id = 1
        self._vocab: list[VocabWord] = []
        self._known_words = known_words

    # Videos
    def save_video(self, video: Video) -> None:
        if video.id is None:
            video.id = self._next_video_id
            self._next_video_id += 1
            self._videos.append(video)
        else:
            for i, v in enumerate(self._videos):
                if v.id == video.id:
                    self._videos[i] = video
                    break

    def get_video(self, youtube_id: str) -> Video | None:
        for v in self._videos:
            if v.youtube_id == youtube_id:
                return v
        return None

    def list_videos(self) -> list[Video]:
        return list(self._videos)

    def video_exists(self, youtube_id: str) -> bool:
        return any(v.youtube_id == youtube_id for v in self._videos)

    # Sentences
    def save_sentences(self, sentences: list[Sentence]) -> None:
        for s in sentences:
            if s.id is None:
                s.id = self._next_sentence_id
                self._next_sentence_id += 1
            self._sentences.append(s)

    def get_sentences_by_video(self, video_id: int, status: str | None = None) -> list[Sentence]:
        results = [s for s in self._sentences if s.video_id == video_id]
        if status:
            results = [s for s in results if s.status == status]
        return results

    def get_stash_candidates(self, limit: int = 20) -> list[Sentence]:
        return [s for s in self._sentences if s.status == "stashed"][:limit]

    def update_sentence(self, sentence: Sentence) -> None:
        for i, s in enumerate(self._sentences):
            if s.id == sentence.id:
                self._sentences[i] = sentence
                break

    def get_sentences_by_status(self, status: str) -> list[Sentence]:
        return [s for s in self._sentences if s.status == status]

    def reclassify_stashed(self, video_id: int) -> int:
        return 0

    # Vocab
    def save_vocab_word(self, word: VocabWord) -> None:
        self._vocab.append(word)

    def get_vocab_word(self, word_simplified: str) -> VocabWord | None:
        for w in self._vocab:
            if w.word_simplified == word_simplified:
                return w
        return None

    def get_known_words(self) -> set[str]:
        return self._known | {w.word_simplified for w in self._vocab if w.status == "known"}

    def mark_word_known(self, word_simplified: str) -> None:
        existing = self.get_vocab_word(word_simplified)
        if existing:
            existing.status = "known"
        else:
            self._vocab.append(VocabWord(word_simplified=word_simplified, status="known"))

    def mark_word_learning(self, word_simplified: str) -> None:
        existing = self.get_vocab_word(word_simplified)
        if existing:
            existing.status = "learning"
        else:
            self._vocab.append(VocabWord(word_simplified=word_simplified, status="learning"))

    def get_vocab_stats(self) -> dict:
        known = sum(1 for w in self._vocab if w.status == "known")
        learning = sum(1 for w in self._vocab if w.status == "learning")
        total = len(self._vocab)
        return {"known": known, "learning": learning, "total": total}

    def list_vocab(
        self, page=1, per_page=200, status=None, search=None, sort="frequency"
    ):
        words = list(self._vocab)
        if status:
            words = [w for w in words if w.status == status]
        if search:
            words = [w for w in words
                     if search.lower() in w.word_simplified.lower()
                     or search.lower() in (w.pinyin or "").lower()]
        # Sort by frequency_rank (None last)
        words.sort(key=lambda w: (w.frequency_rank is None, w.frequency_rank or 999999))
        total = len(words)
        start = (page - 1) * per_page
        return words[start:start + per_page], total

    def get_sentences_by_word(self, word: str) -> list[Sentence]:
        return [s for s in self._sentences
                if s.unknown_word == word or word in s.text]


class FakeTranscriptSource(TranscriptSource):
    """Fake transcript source — returns hardcoded Chinese sentences."""

    def fetch(self, video_id: str) -> list[TranscriptChunk]:
        return [
            TranscriptChunk(text="我们", start_ms=0, duration_ms=500),
            TranscriptChunk(text="一般", start_ms=600, duration_ms=400),
            TranscriptChunk(text="早上", start_ms=1100, duration_ms=400),
            TranscriptChunk(text="七点", start_ms=1600, duration_ms=300),
            TranscriptChunk(text="起床", start_ms=2000, duration_ms=500),
            TranscriptChunk(text="我", start_ms=3000, duration_ms=300),
            TranscriptChunk(text="爱", start_ms=3400, duration_ms=300),
            TranscriptChunk(text="学习", start_ms=3800, duration_ms=500),
        ]


class FakeAudioProcessor(AudioProcessor):
    """Fake audio processor — returns paths without real files."""

    def download(self, video_id: str, output_dir: str) -> str:
        return f"{output_dir}/{video_id}.mp3"

    def clip(
        self, audio_path, start_ms, end_ms,
        pad_before_ms, pad_after_ms, output_dir, sentence_id,
    ) -> str:
        return f"{output_dir}/{sentence_id}.mp3"

    def capture_frame(
        self, video_id, timestamp_ms, output_dir, sentence_id,
    ) -> str | None:
        return f"{output_dir}/frame_{sentence_id}.jpg"


# === Fixtures ===


@pytest.fixture
def persistence():
    """Fresh FakePersistence with known vocab."""
    return FakePersistence(known_words={"我们", "早上", "起床", "学习", "我", "爱", "你"})


@pytest.fixture
def processor():
    """Fake Chinese language processor."""
    return FakeLanguageProcessor()


@pytest.fixture
def transcript():
    """Fake transcript source."""
    return FakeTranscriptSource()


@pytest.fixture
def audio():
    """Fake audio processor."""
    return FakeAudioProcessor()


@pytest.fixture
def client(persistence, processor, transcript, audio):
    """Flask test client with fake ports injected."""
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
def client_with_sentences(client, persistence):
    """Test client with a pre-populated video and sentences."""
    # Create a video
    video = Video(youtube_id="dQw4w9WgXcQ", title="Test Video", channel="Test Channel")
    persistence.save_video(video)

    # Create sentences with various statuses
    sentences = [
        Sentence(
            video_id=video.id, start_ms=1000, end_ms=3000,
            text="我们 一般 早上 起床", text_segmented="我们 / 一般 / 早上 / 起床",
            unknown_word="一般", unknown_word_rank=1847,
            audio_clip_path="/tmp/clips/s1.mp3", status="i1",
        ),
        Sentence(
            video_id=video.id, start_ms=4000, end_ms=7000,
            text="我 爱 学习", text_segmented="我 / 爱 / 学习",
            audio_clip_path="/tmp/clips/s2.mp3", status="i0",
        ),
        Sentence(
            video_id=video.id, start_ms=8000, end_ms=12000,
            text="今天 天气 很 好 啊", text_segmented="今天 / 天气 / 很 / 好 / 啊",
            audio_clip_path="/tmp/clips/s3.mp3", status="stashed",
        ),
        Sentence(
            video_id=video.id, start_ms=13000, end_ms=16000,
            text="已经 保存 了", text_segmented="已经 / 保存 / 了",
            unknown_word="保存", unknown_word_rank=5200,
            audio_clip_path="/tmp/clips/s4.mp3", status="kept",
        ),
    ]
    for s in sentences:
        persistence.save_sentences([s])

    return client, persistence


@pytest.fixture
def client_with_anki(client, persistence, processor, transcript, audio):
    """Flask test client with a fake AnkiExporter injected."""
    from unittest.mock import MagicMock

    mock_exporter = MagicMock()
    mock_exporter.export.return_value = {
        "note_ids": [], "added": 0, "duplicates": 0, "errors": [],
    }

    from langmine.web.app import create_app
    app = create_app(
        persistence=persistence,
        language_processor=processor,
        transcript_source=transcript,
        audio_processor=audio,
        anki_exporter=mock_exporter,
    )
    app.config["TESTING"] = True
    return app.test_client()


# === Tests ===


class TestListVideos:
    """GET /api/videos"""

    def test_empty_library(self, client):
        """Returns empty list when no videos mined."""
        resp = client.get("/api/videos")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data == {"videos": []}

    def test_videos_with_sentence_counts(self, client_with_sentences):
        """Returns videos with counts of sentences by status."""
        client, _ = client_with_sentences
        resp = client.get("/api/videos")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert len(data["videos"]) == 1
        v = data["videos"][0]
        assert v["youtube_id"] == "dQw4w9WgXcQ"
        assert v["title"] == "Test Video"
        assert v["channel"] == "Test Channel"
        assert v["id"] == 1
        assert v["total_sentences"] == 4
        assert v["i1_count"] == 1
        assert v["i0_count"] == 1
        assert v["stashed_count"] == 1
        assert v["kept_count"] == 1


class TestMineVideo:
    """POST /api/videos/mine"""

    def test_mine_requires_url_field(self, client):
        """Returns 400 when no url is provided."""
        resp = client.post(
            "/api/videos/mine",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert "url" in json.loads(resp.data)["error"].lower()

    def test_mine_processes_video_with_fake_ports(self, client, persistence):
        """Mining a video with fake ports creates it in persistence."""
        resp = client.post(
            "/api/videos/mine",
            data=json.dumps({"url": "https://youtube.com/watch?v=testVid1234"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["youtube_id"] == "testVid1234"
        assert data["total_sentences"] > 0
        assert "i1_count" in data
        assert "stash_count" in data

        # Video should be persisted
        video = persistence.get_video("testVid1234")
        assert video is not None
        assert video.youtube_id == "testVid1234"

        # Sentences should be persisted
        sentences = persistence.get_sentences_by_video(video.id)
        assert len(sentences) > 0


class TestGetSentences:
    """GET /api/videos/<video_id>/sentences"""

    def test_all_sentences_for_video(self, client_with_sentences):
        """Returns all sentences for a video."""
        client, _ = client_with_sentences
        resp = client.get("/api/videos/1/sentences")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert len(data["sentences"]) == 4

    def test_filter_by_status(self, client_with_sentences):
        """Returns only sentences with given status."""
        client, _ = client_with_sentences
        resp = client.get("/api/videos/1/sentences?status=i1")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert len(data["sentences"]) == 1
        assert data["sentences"][0]["status"] == "i1"
        assert data["sentences"][0]["unknown_word"] == "一般"

    def test_unknown_video_returns_empty(self, client):
        """Non-existent video returns empty list."""
        resp = client.get("/api/videos/999/sentences")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["sentences"] == []

    def test_sentence_includes_all_fields(self, client_with_sentences):
        """Each sentence object has all expected fields."""
        client, _ = client_with_sentences
        resp = client.get("/api/videos/1/sentences?status=i1")
        data = json.loads(resp.data)
        sentence = data["sentences"][0]
        assert "id" in sentence
        assert "video_id" in sentence
        assert "text" in sentence
        assert "text_segmented" in sentence
        assert "unknown_word" in sentence
        assert "unknown_word_rank" in sentence
        assert "status" in sentence
        assert "has_audio" in sentence


class TestUpdateSentence:
    """PATCH /api/sentences/<sentence_id>"""

    def test_mark_kept(self, client_with_sentences):
        """Marking a sentence as 'kept' updates its status."""
        client, persistence = client_with_sentences
        resp = client.patch(
            "/api/sentences/1",
            data=json.dumps({"status": "kept"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["sentence"]["status"] == "kept"

        # Verify persistence was updated
        sentences = persistence.get_sentences_by_video(1)
        s = [s for s in sentences if s.id == 1][0]
        assert s.status == "kept"

    def test_mark_deleted(self, client_with_sentences):
        """Marking a sentence as 'deleted' updates its status."""
        client, _ = client_with_sentences
        resp = client.patch(
            "/api/sentences/1",
            data=json.dumps({"status": "deleted"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert json.loads(resp.data)["sentence"]["status"] == "deleted"

    def test_unknown_sentence_returns_404(self, client):
        """Non-existent sentence returns 404."""
        resp = client.patch(
            "/api/sentences/999",
            data=json.dumps({"status": "kept"}),
            content_type="application/json",
        )
        assert resp.status_code == 404

    def test_invalid_status_returns_400(self, client_with_sentences):
        """Invalid status value returns 400."""
        client, _ = client_with_sentences
        resp = client.patch(
            "/api/sentences/1",
            data=json.dumps({"status": "invalid"}),
            content_type="application/json",
        )
        assert resp.status_code == 400


class TestIknowthis:
    """PATCH /api/sentences/<sentence_id>/iknowthis"""

    def test_marks_word_known(self, client_with_sentences):
        """i-know-this marks the unknown word as known."""
        client, persistence = client_with_sentences
        resp = client.patch("/api/sentences/1/iknowthis")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["word_marked"] == "一般"

        # Word should be marked as known
        assert "一般" in persistence.get_known_words()

        # Sentence should be reclassified to i0 (all words now known)
        sentences = persistence.get_sentences_by_video(1)
        s = [s for s in sentences if s.id == 1][0]
        assert s.status == "i0"

    def test_no_unknown_word_returns_400(self, client_with_sentences):
        """i+0 sentence (no unknown word) should return 400."""
        client, _ = client_with_sentences
        # Sentence 2 is i0 (no unknown word)
        resp = client.patch("/api/sentences/2/iknowthis")
        assert resp.status_code == 400

    def test_unknown_sentence_returns_404(self, client):
        """Non-existent sentence returns 404."""
        resp = client.patch("/api/sentences/999/iknowthis")
        assert resp.status_code == 404


class TestSentenceAudio:
    """GET /api/sentences/<sentence_id>/audio"""

    def test_returns_404_if_no_audio_file(self, client_with_sentences):
        """When audio file doesn't exist, returns 404."""
        client, _ = client_with_sentences
        resp = client.get("/api/sentences/1/audio")
        # Audio file at /tmp/clips/s1.mp3 doesn't exist in test — returns 404
        assert resp.status_code == 404

    def test_unknown_sentence_returns_404(self, client):
        """Non-existent sentence returns 404."""
        resp = client.get("/api/sentences/999/audio")
        assert resp.status_code == 404


class TestStats:
    """GET /api/stats"""

    def test_initial_stats(self, client, persistence):
        """Returns vocab stats with HSK bootstrap words."""
        resp = client.get("/api/stats")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "known" in data
        assert "learning" in data
        assert isinstance(data["known"], int)
        assert isinstance(data["learning"], int)

    def test_stats_after_iknowthis(self, client_with_sentences):
        """Stats update after marking a word known."""
        client, _ = client_with_sentences
        # Initial stats
        before = json.loads(client.get("/api/stats").data)
        initial_known = before["known"]

        # Mark a word known
        client.patch("/api/sentences/1/iknowthis")

        after = json.loads(client.get("/api/stats").data)
        assert after["known"] > initial_known


class TestAnkiExport:
    """POST /api/export/anki"""

    def test_503_when_no_exporter_configured(self, client):
        """Returns 503 if AnkiExporter not injected."""
        resp = client.post("/api/export/anki", json={"all_kept": True})
        assert resp.status_code == 503
        data = json.loads(resp.data)
        assert "error" in data

    def test_400_when_no_kept_sentences(self, client_with_anki):
        """Returns 400 when no kept sentences exist."""
        client = client_with_anki
        resp = client.post("/api/export/anki", json={"all_kept": True})
        assert resp.status_code == 400

    def test_cloze_card_type_passed_to_exporter(self, client_with_sentences):
        """POST with card_type='cloze' passes it to the AnkiExporter."""
        from unittest.mock import MagicMock, patch
        from langmine.web.app import create_app
        from tests.test_web_api import (
            FakePersistence, FakeLanguageProcessor, FakeTranscriptSource,
            FakeAudioProcessor,
        )

        # Create a fresh app with a mock exporter that we can inspect
        persistence = FakePersistence(known_words={"我们", "早上", "起床", "学习", "我", "爱", "你"})
        video = Video(youtube_id="test", title="T", channel="C")
        persistence.save_video(video)
        sentence = Sentence(
            video_id=video.id, start_ms=1000, end_ms=3000,
            text="我们 一般 早上 起床", text_segmented="我们 / 一般 / 早上 / 起床",
            unknown_word="一般", unknown_word_rank=1847,
            status="kept",
        )
        persistence.save_sentences([sentence])

        mock_exporter = MagicMock()
        mock_exporter.export.return_value = {
            "note_ids": [], "added": 0, "duplicates": 0, "errors": [],
        }

        app = create_app(
            persistence=persistence,
            language_processor=FakeLanguageProcessor(),
            transcript_source=FakeTranscriptSource(),
            audio_processor=FakeAudioProcessor(),
            anki_exporter=mock_exporter,
        )
        app.config["TESTING"] = True
        client = app.test_client()

        resp = client.post(
            "/api/export/anki",
            json={"all_kept": True, "card_type": "cloze"},
        )
        assert resp.status_code == 200

        # Verify mock received card_type
        mock_exporter.export.assert_called_once()
        call_kwargs = mock_exporter.export.call_args.kwargs
        assert call_kwargs.get("card_type") == "cloze", (
            f"Expected card_type='cloze', got {call_kwargs.get('card_type')}"
        )


class TestSPAServing:
    """GET / serves the Svelte SPA."""

    def test_serves_html_page(self, client):
        """Root URL returns the Svelte-built index.html."""
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"<!DOCTYPE html>" in resp.data or b"<html" in resp.data
        assert b"LangMine" in resp.data

    def test_static_assets_served(self, client):
        """Built Svelte assets are served from /assets/ path."""
        resp = client.get("/favicon.svg")
        assert resp.status_code == 200


class TestSentenceEdits:
    """PATCH /api/sentences/<id> with field edits."""

    def test_edit_pinyin(self, client_with_sentences):
        """Should update pinyin field."""
        client, _ = client_with_sentences
        resp = client.patch(
            "/api/sentences/1",
            data=json.dumps({"pinyin": "wǒmen yībān zǎoshang qǐchuáng"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["sentence"]["pinyin"] == "wǒmen yībān zǎoshang qǐchuáng"

    def test_edit_translation(self, client_with_sentences):
        """Should update translation_de field."""
        client, _ = client_with_sentences
        resp = client.patch(
            "/api/sentences/1",
            data=json.dumps({"translation_de": "Wir stehen normalerweise morgens auf"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["sentence"]["translation_de"] == "Wir stehen normalerweise morgens auf"

    def test_edit_multiple_fields(self, client_with_sentences):
        """Should update pinyin and translation in one request."""
        client, _ = client_with_sentences
        resp = client.patch(
            "/api/sentences/1",
            data=json.dumps({
                "pinyin": "new pinyin",
                "translation_de": "new translation",
            }),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["sentence"]["pinyin"] == "new pinyin"
        assert data["sentence"]["translation_de"] == "new translation"

    def test_edit_and_status_together(self, client_with_sentences):
        """Should handle both field edit and status change."""
        client, _ = client_with_sentences
        resp = client.patch(
            "/api/sentences/1",
            data=json.dumps({
                "pinyin": "corrected pinyin",
                "status": "kept",
            }),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["sentence"]["pinyin"] == "corrected pinyin"
        assert data["sentence"]["status"] == "kept"

    def test_reclassify_on_segmentation_change(self, client_with_sentences):
        """Changing text_segmented should re-classify (i1 → i0 if all known)."""
        # Sentence 1: "我们 / 一般 / 早上 / 起床" with 一般 as unknown
        # Change so all words are known: "我们 / 早上 / 起床"
        client, _ = client_with_sentences
        resp = client.patch(
            "/api/sentences/1",
            data=json.dumps({"text_segmented": "我们 / 早上 / 起床"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["sentence"]["status"] == "i0"
        assert data["sentence"]["unknown_word"] is None

    def test_reclassify_to_stashed(self, client_with_sentences):
        """Adding more unknown words should push to stashed."""
        # Change to have 2 unknowns: "一般 / 爬山" both unknown
        client, _ = client_with_sentences
        resp = client.patch(
            "/api/sentences/1",
            data=json.dumps({"text_segmented": "一般 / 爬山 / 起床"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["sentence"]["status"] == "stashed"
        assert data["sentence"]["unknown_word"] is None

    def test_unknown_sentence_returns_404(self, client):
        """Should return 404 for non-existent sentence."""
        resp = client.patch(
            "/api/sentences/999",
            data=json.dumps({"pinyin": "test"}),
            content_type="application/json",
        )
        assert resp.status_code == 404

    def test_empty_body_returns_400(self, client):
        """Should return 400 for empty request body."""
        resp = client.patch(
            "/api/sentences/1",
            data=None,
            content_type="application/json",
        )
        assert resp.status_code == 400


class TestConfigAPI:
    """GET/PUT /api/config."""

    def test_get_config_returns_values(self, client):
        """Should return all config values (no API keys)."""
        resp = client.get("/api/config")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "deck_name" in data
        assert "source_language" in data
        assert "max_cards_per_video" in data
        # API keys should NOT be in response
        assert "deepl_api_key" not in data

    def test_put_config_updates_values(self, client):
        """Should update config values."""
        resp = client.put(
            "/api/config",
            data=json.dumps({
                "deck_name": "Custom Deck",
                "max_cards_per_video": 10,
            }),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert json.loads(resp.data)["ok"] is True

    def test_put_config_empty_body_returns_400(self, client):
        """Should return 400 for empty body."""
        resp = client.put("/api/config", data=None, content_type="application/json")
        assert resp.status_code == 400


class TestTranscriptEndpoint:
    """GET /api/videos/<id>/transcript — reading view endpoint."""

    def test_returns_ordered_sentences(self, client_with_sentences):
        """Transcript endpoint returns sentences sorted by start_ms."""
        client, _ = client_with_sentences
        resp = client.get("/api/videos/1/transcript")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "sentences" in data
        assert len(data["sentences"]) > 0
        starts = [s["start_ms"] for s in data["sentences"]]
        assert starts == sorted(starts)

    def test_returns_full_metadata(self, client_with_sentences):
        """Each sentence has text, pinyin, translation, words array, status."""
        client, _ = client_with_sentences
        resp = client.get("/api/videos/1/transcript")
        data = json.loads(resp.data)
        sentence = data["sentences"][0]
        assert "text" in sentence
        assert "pinyin" in sentence
        assert "translation_de" in sentence
        assert "words" in sentence
        assert "status" in sentence
        assert "has_audio" in sentence

    def test_includes_deleted_sentences(self, client_with_sentences):
        """Reading view shows all sentences including deleted, for context."""
        client, _ = client_with_sentences
        # Mark sentence 1 as deleted
        client.patch(
            "/api/sentences/1",
            data=json.dumps({"status": "deleted"}),
            content_type="application/json",
        )
        resp = client.get("/api/videos/1/transcript")
        data = json.loads(resp.data)
        statuses = [s["status"] for s in data["sentences"]]
        assert "deleted" in statuses

    def test_unknown_video_returns_empty(self, client):
        """Non-existent video returns empty sentence list."""
        resp = client.get("/api/videos/999/transcript")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["sentences"] == []
