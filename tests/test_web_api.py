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
    def get_annotation(self, text): return "[]"


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

    def list_videos(self, language_code: str = "") -> list[Video]:
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

    def get_sentences_by_video(self, video_id: int, status: str | None = None, language_code: str = "") -> list[Sentence]:
        results = [s for s in self._sentences if s.video_id == video_id]
        if status:
            results = [s for s in results if s.status == status]
        return results

    def get_stash_candidates(self, limit: int = 20, language_code: str = "") -> list[Sentence]:
        return [s for s in self._sentences if s.status == "stashed"][:limit]

    def update_sentence(self, sentence: Sentence) -> None:
        for i, s in enumerate(self._sentences):
            if s.id == sentence.id:
                self._sentences[i] = sentence
                break

    def get_sentences_by_status(self, status: str, language_code: str = "") -> list[Sentence]:
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

    def get_known_words(self, language_code: str = "") -> set[str]:
        return self._known | {w.word_simplified for w in self._vocab if w.status in ("known", "ignored")}

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

    def mark_word_ignored(self, word_simplified: str) -> None:
        existing = self.get_vocab_word(word_simplified)
        if existing:
            existing.status = "ignored"
        else:
            self._vocab.append(VocabWord(word_simplified=word_simplified, status="ignored"))

    def get_vocab_stats(self, language_code: str = "") -> dict:
        known = sum(1 for w in self._vocab if w.status == "known")
        learning = sum(1 for w in self._vocab if w.status == "learning")
        ignored = sum(1 for w in self._vocab if w.status == "ignored")
        total = len(self._vocab)
        return {"known": known, "learning": learning, "ignored": ignored, "total": total}

    def list_vocab(
        self, page=1, per_page=200, status=None, search=None, sort="frequency"
    ):
        words = list(self._vocab)
        if status:
            words = [w for w in words if w.status == status]
        if search:
            words = [w for w in words
                     if search.lower() in w.word_simplified.lower()
                     or search.lower() in (w.reading or "").lower()]
        # Sort by frequency_rank (None last)
        words.sort(key=lambda w: (w.frequency_rank is None, w.frequency_rank or 999999))
        total = len(words)
        start = (page - 1) * per_page
        return words[start:start + per_page], total

    def get_sentences_by_word(self, word: str) -> list[Sentence]:
        return [s for s in self._sentences
                if s.unknown_word == word or word in s.text]

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


class TestLanguagesEndpoint:
    """GET /api/languages returns available language codes and names."""

    def test_returns_language_list(self, client):
        """Returns [{code, name}] for all registered languages."""
        resp = client.get("/api/languages")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "languages" in data
        langs = data["languages"]
        assert isinstance(langs, list)
        assert len(langs) >= 1

        # Chinese must be present (the only registered language so far)
        codes = {lang["code"] for lang in langs}
        assert "zh" in codes

        # Each entry has code and name
        zh = next(lang for lang in langs if lang["code"] == "zh")
        assert "name" in zh
        assert isinstance(zh["name"], str)
        assert len(zh["name"]) > 0

    def test_chinese_is_listed(self, client):
        """Chinese language info is correct."""
        resp = client.get("/api/languages")
        data = resp.get_json()
        zh = [l for l in data["languages"] if l["code"] == "zh"]
        assert len(zh) == 1
        assert zh[0]["name"] in ("中文", "Chinese")  # either is fine
