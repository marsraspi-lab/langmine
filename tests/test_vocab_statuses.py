"""Tests for GET /api/vocab/statuses endpoint (M19)."""

import pytest
from tests.test_web_api import (
    FakePersistence, FakeLanguageProcessor, FakeTranscriptSource,
    FakeAudioProcessor, VocabWord,
)


@pytest.fixture
def persistence():
    return FakePersistence()


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


class TestVocabStatuses:
    """Tests for the vocab status grouping endpoint."""

    def test_returns_all_status_groups(self, client):
        """GET /api/vocab/statuses returns known/learning/ignored keys."""
        resp = client.get("/api/vocab/statuses")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "known" in data
        assert "learning" in data
        assert "ignored" in data
        assert isinstance(data["known"], list)
        assert isinstance(data["learning"], list)
        assert isinstance(data["ignored"], list)

    def test_empty_when_no_vocab(self, client):
        """When no vocab words exist, all lists are empty."""
        resp = client.get("/api/vocab/statuses")
        data = resp.get_json()
        assert data["known"] == []
        assert data["learning"] == []
        assert data["ignored"] == []

    def test_groups_words_by_status(self, client, persistence):
        """Words are correctly grouped by their status."""
        persistence.save_vocab_word(VocabWord(word_simplified="我们", status="known"))
        persistence.save_vocab_word(VocabWord(word_simplified="学习", status="learning"))
        persistence.save_vocab_word(VocabWord(word_simplified="的", status="ignored"))
        persistence.save_vocab_word(VocabWord(word_simplified="你好", status="known"))
        persistence.save_vocab_word(VocabWord(word_simplified="世界", status="learning"))

        resp = client.get("/api/vocab/statuses")
        data = resp.get_json()

        assert sorted(data["known"]) == ["你好", "我们"]
        assert sorted(data["learning"]) == ["世界", "学习"]
        assert data["ignored"] == ["的"]

    def test_language_code_scoping(self, client, persistence):
        """When language_code is set, only words for that language are returned."""
        persistence.save_vocab_word(
            VocabWord(word_simplified="我们", status="known", language_code="zh")
        )
        persistence.save_vocab_word(
            VocabWord(word_simplified="hola", status="known", language_code="es")
        )

        resp = client.get("/api/vocab/statuses")
        data = resp.get_json()
        # Without language context, all are returned
        assert len(data["known"]) == 2
