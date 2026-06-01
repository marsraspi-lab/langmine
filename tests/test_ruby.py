"""Tests for M14 ruby annotations — character-level pinyin with tone colors."""

import json
import pytest

from langmine.domain.ports import (
    LanguageProcessor, Persistence, TranscriptSource, AudioProcessor,
    TranscriptChunk,
)
from langmine.domain.models import Sentence, Video
from langmine.domain.classifier import SentenceClassifier


# === Fake ports ===

class FakeRubyProcessor(LanguageProcessor):
    """Returns predictable ruby data for testing."""

    def segment(self, text):
        return list(text)

    def get_reading(self, text):
        return " ".join(f"py:{c}" for c in text)

    def lookup_word(self, word):
        return {"definition_de": f"def:{word}", "definition_en": f"def:{word}"}

    def translate_sentence(self, text):
        return f"[DE] {text}"

    def get_frequency(self, word):
        return 1000

    def is_non_word(self, token):
        return token in {"的", "了", "吗", "啊", "呢", "吧"}

    def is_proper_name(self, token, context_sentence=""): return False

    def find_known_synonyms(self, word, known_words):
        return []

    def get_annotation(self, text: str) -> str:
        """Return ruby JSON for text: one entry per character."""
        entries = []
        for char in text:
            # Simulate tone: vowels get tone 1, consonants get tone 4
            if char in "aeiouAEIOU":
                tone = 1
            elif char.isalpha():
                tone = 4
            else:
                tone = 5  # neutral for non-letters
            entries.append({
                "char": char,
                "pinyin": f"py:{char}",
                "tone": tone,
            })
        return json.dumps(entries)


class FakePersistence:
    """Minimal fake for classifier testing."""

    def __init__(self, known_words=None):
        self._known = known_words or set()
        self._ignored = set()

    def get_known_words(self):
        return self._known | self._ignored


# === Tests: Ruby generation ===

class TestRubyGeneration:
    """get_annotation() produces character-level pinyin + tone data."""

    def test_ruby_returns_valid_json_array(self):
        """get_annotation returns a JSON array of character entries."""
        processor = FakeRubyProcessor()
        result = processor.get_annotation("abc")
        data = json.loads(result)

        assert isinstance(data, list)
        assert len(data) == 3

    def test_ruby_each_entry_has_char_pinyin_tone(self):
        """Each entry has char, pinyin, and tone fields."""
        processor = FakeRubyProcessor()
        result = processor.get_annotation("ab")
        data = json.loads(result)

        for entry in data:
            assert "char" in entry
            assert "pinyin" in entry
            assert "tone" in entry

    def test_ruby_tone_is_int_1_to_5(self):
        """Tone values are integers 1-5 (Pleco convention)."""
        processor = FakeRubyProcessor()
        result = processor.get_annotation("a你")
        data = json.loads(result)

        for entry in data:
            assert isinstance(entry["tone"], int)
            assert 1 <= entry["tone"] <= 5

    def test_ruby_char_count_matches_text_length(self):
        """Number of entries equals number of characters in input text."""
        processor = FakeRubyProcessor()
        for text in ["你好", "hello world", "测试abc", ""]:
            result = processor.get_annotation(text)
            data = json.loads(result)
            assert len(data) == len(text), (
                f"Text '{text}' ({len(text)} chars) → {len(data)} entries"
            )


# === Tests: Sentence enrichment ===

class TestRubyEnrichment:
    """SentenceClassifier.enrich() populates annotation_json on sentences."""

    def test_enrich_populates_annotation_json(self):
        """After enrich(), sentences have non-empty annotation_json."""
        processor = FakeRubyProcessor()
        persistence = FakePersistence(known_words={"你", "好"})
        classifier = SentenceClassifier(processor, persistence)

        sentences = [
            Sentence(
                video_id=1, start_ms=0, end_ms=1000,
                text="你好", text_segmented="你 / 好",
                status="i1", unknown_word="你好",
            )
        ]
        classifier.enrich(sentences)

        assert sentences[0].annotation_json, "annotation_json should not be empty"
        data = json.loads(sentences[0].annotation_json)
        assert len(data) == 2  # 你, 好

    def test_annotation_json_matches_text_length(self):
        """annotation_json has one entry per character."""
        processor = FakeRubyProcessor()
        persistence = FakePersistence()
        classifier = SentenceClassifier(processor, persistence)

        sentences = [
            Sentence(
                video_id=1, start_ms=0, end_ms=1000,
                text="测试文本", text_segmented="测试 / 文本",
                status="kept",
            )
        ]
        classifier.enrich(sentences)

        data = json.loads(sentences[0].annotation_json)
        assert len(data) == 4  # 测, 试, 文, 本


# === Tests: API integration ===

class TestRubyAPI:
    """Sentence API response includes ruby field."""

    def test_sentence_to_dict_includes_ruby(self):
        """_sentence_to_dict returns ruby field from annotation_json."""
        from langmine.web.routes import _sentence_to_dict

        ruby = json.dumps([
            {"char": "你", "pinyin": "ni3", "tone": 3},
            {"char": "好", "pinyin": "hao3", "tone": 3},
        ])

        sentence = Sentence(
            id=1, video_id=1,
            start_ms=0, end_ms=1000,
            text="你好", text_segmented="你 / 好",
            reading="ni3 hao3", translation_de="Hallo",
            annotation_json=ruby, status="kept",
        )

        result = _sentence_to_dict(sentence)
        assert "annotation" in result
        assert result["annotation"] is not None
        data = result["annotation"]
        assert len(data) == 2
        assert data[0]["char"] == "你"
        assert data[0]["tone"] == 3

    def test_sentence_to_dict_handles_empty_ruby(self):
        """Empty annotation_json returns empty list."""
        from langmine.web.routes import _sentence_to_dict

        sentence = Sentence(
            id=1, video_id=1,
            start_ms=0, end_ms=1000,
            text="你好", text_segmented="你 / 好",
            annotation_json="", status="kept",
        )

        result = _sentence_to_dict(sentence)
        assert result["annotation"] == []

    def test_sentence_to_dict_handles_invalid_annotation_json(self):
        """Invalid annotation_json returns empty list (graceful)."""
        from langmine.web.routes import _sentence_to_dict

        sentence = Sentence(
            id=1, video_id=1,
            start_ms=0, end_ms=1000,
            text="你好", text_segmented="你 / 好",
            annotation_json="{invalid json", status="kept",
        )

        result = _sentence_to_dict(sentence)
        assert result["annotation"] == []


# === Tests: Ruby edit API ===

import json as _json


# Minimal fake ports for API tests
class FakeRbProcessor(LanguageProcessor):
    def segment(self, text): return text.split()
    def get_reading(self, text): return " ".join(f"py:{t}" for t in text.split())
    def lookup_word(self, word): return {"definition_de": f"def:{word}", "definition_en": f"def:{word}"}
    def translate_sentence(self, text): return f"[DE] {text}"
    def get_frequency(self, word): return 1000
    def is_non_word(self, token): return token in {"的", "了", "吗", "啊", "呢", "吧"}
    def is_proper_name(self, token, context_sentence=""): return False
    def find_known_synonyms(self, word, known_words): return []
    def get_annotation(self, text): return "[]"


class FakeRbPersistence(Persistence):
    def __init__(self):
        self._ignored = set()
        self._videos = []
        self._sentences = []
        self._next_vid = 1
        self._next_sid = 1

    def save_video(self, v):
        if v.id is None: v.id = self._next_vid; self._next_vid += 1; self._videos.append(v)
    def list_videos(self): return self._videos
    def get_video(self, yt_id):
        for v in self._videos:
            if v.youtube_id == yt_id: return v
        return None
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
    def get_known_words(self): return self._ignored
    def get_vocab_word(self, w): return None
    def save_vocab_word(self, w): pass
    def mark_word_known(self, w): pass
    def mark_word_learning(self, w): pass
    def get_vocab_stats(self): return {"known": 0, "learning": 0, "total": 0}
    def list_vocab(self, **kw): return [], 0
    def get_sentences_by_word(self, w): return []

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
        pass

    def get_stash_candidates(self, limit=20): return []
    def get_sentences_by_status(self, status): return []
    def reclassify_stashed(self, vid): return 0


class FakeRbTranscript(TranscriptSource):
    def fetch(self, video_id, language=""): return [TranscriptChunk(text="test", start_ms=0, duration_ms=500)]
    def list_subtitles(self, video_id): return []


class FakeRbAudio(AudioProcessor):
    def download(self, video_id, output_dir): return "/tmp/test.mp3"
    def clip(self, *args, **kwargs): return "/tmp/clip.mp3"
    def capture_frame(self, *args, **kwargs): return None


@pytest.fixture
def rb_persistence():
    return FakeRbPersistence()


@pytest.fixture
def rb_client(rb_persistence):
    from langmine.web.app import create_app
    app = create_app(
        persistence=rb_persistence,
        language_processor=FakeRbProcessor(),
        transcript_source=FakeRbTranscript(),
        audio_processor=FakeRbAudio(),
    )
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture
def client_with_ruby_sentence(rb_client, rb_persistence):
    """Seed a sentence with pre-populated annotation_json."""
    video = Video(youtube_id="test12345678", title="Test", channel="C")
    rb_persistence.save_video(video)
    ruby = _json.dumps([
        {"char": "你", "pinyin": "ni", "tone": 3},
        {"char": "好", "pinyin": "hao", "tone": 3},
    ])
    sentence = Sentence(
        video_id=video.id, start_ms=0, end_ms=1000,
        text="你好", text_segmented="你 / 好",
        annotation_json=ruby, status="kept",
    )
    rb_persistence.save_sentences([sentence])
    return rb_client, sentence


class TestRubyEditEndpoint:
    """PATCH /api/sentences/:id/annotation — update a single ruby entry."""

    def test_update_single_ruby_entry(self, client_with_ruby_sentence):
        """Updating one character's pinyin and tone persists the change."""
        client, sentence = client_with_ruby_sentence

        resp = client.patch(
            f"/api/sentences/{sentence.id}/annotation",
            json={"index": 0, "pinyin": "ni3", "tone": 3},
        )
        assert resp.status_code == 200
        data = _json.loads(resp.data)
        assert data["ok"] is True
        assert data["annotation"][0]["pinyin"] == "ni3"
        assert data["annotation"][0]["tone"] == 3
        assert data["annotation"][1]["char"] == "好"

    def test_ruby_edit_rejects_invalid_index(self, client_with_ruby_sentence):
        """Index out of range returns 400."""
        client, sentence = client_with_ruby_sentence

        resp = client.patch(
            f"/api/sentences/{sentence.id}/annotation",
            json={"index": 99, "pinyin": "x"},
        )
        assert resp.status_code == 400
        data = _json.loads(resp.data)
        assert "error" in data

    def test_ruby_edit_rejects_missing_index(self, client_with_ruby_sentence):
        """Missing index returns 400."""
        client, sentence = client_with_ruby_sentence

        resp = client.patch(
            f"/api/sentences/{sentence.id}/annotation",
            json={"reading": "ni"},
        )
        assert resp.status_code == 400

    def test_ruby_edit_404_for_nonexistent_sentence(self, rb_client):
        """Nonexistent sentence returns 404."""
        resp = rb_client.patch(
            "/api/sentences/999/annotation",
            json={"index": 0, "pinyin": "ni"},
        )
        assert resp.status_code == 404
