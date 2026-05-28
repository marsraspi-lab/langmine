"""Tests for AnkiConnectAdapter."""

import os
import tempfile
from unittest.mock import patch, MagicMock

import pytest

from langmine.domain.models import Sentence
from langmine.adapters.anki_connect import AnkiConnectAdapter


@pytest.fixture
def adapter():
    return AnkiConnectAdapter(url="http://localhost:8765")


@pytest.fixture
def sample_sentences():
    return [
        Sentence(
            id=1, video_id=1, start_ms=0, end_ms=1000,
            text="你好", pinyin="nǐ hǎo",
            translation_de="Hallo", unknown_word="你好",
            status="kept",
        ),
    ]


def test_implements_port(adapter):
    """AnkiConnectAdapter should implement AnkiExporter port."""
    from langmine.domain.ports import AnkiExporter
    assert isinstance(adapter, AnkiExporter)


def test_export_checks_connectivity(adapter, sample_sentences):
    """Should raise ConnectionError if AnkiConnect not reachable."""
    with patch("requests.post") as mock_post:
        mock_post.side_effect = Exception("Connection refused")
        with pytest.raises(ConnectionError, match="AnkiConnect"):
            adapter.export(sample_sentences)


def test_export_sends_correct_actions(adapter, sample_sentences):
    """Should send createDeck, createModel, canAddNotes, addNotes."""
    with patch("requests.post") as mock_post:
        def side_effect(*args, **kwargs):
            action = kwargs["json"]["action"]
            if action == "canAddNotes":
                return MagicMock(
                    status_code=200,
                    json=lambda: {"result": [None], "error": None},
                )
            return MagicMock(
                status_code=200,
                json=lambda: {"result": [42], "error": None},
            )

        mock_post.side_effect = side_effect

        result = adapter.export(sample_sentences)

        assert result["added"] == 1
        assert result["duplicates"] == 0

        # Verify sequence of actions
        actions = [c[1]["json"]["action"] for c in mock_post.call_args_list]
        assert "createDeck" in actions
        assert "createModel" in actions
        assert "canAddNotes" in actions
        assert "addNotes" in actions


def test_export_handles_audio(adapter):
    """Should call storeMediaFile for sentences with audio clips."""
    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = os.path.join(tmpdir, "test.mp3")
        with open(audio_path, "wb") as f:
            f.write(b"\xff\xfb\x90\x00" * 100)

        sentences = [
            Sentence(
                id=1, video_id=1, start_ms=0, end_ms=1000,
                text="你好", pinyin="nǐ hǎo",
                translation_de="Hallo", unknown_word="你好",
                audio_clip_path=audio_path, status="kept",
            ),
        ]

        with patch("requests.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: {"result": [1], "error": None},
            )
            adapter.export(sentences)

            actions = [c[1]["json"]["action"] for c in mock_post.call_args_list]
            assert "storeMediaFile" in actions


def test_export_returns_summary(adapter, sample_sentences):
    """Should return dict with added count and note IDs."""
    with patch("requests.post") as mock_post:
        def side_effect(*args, **kwargs):
            action = kwargs["json"]["action"]
            if action == "canAddNotes":
                return MagicMock(
                    status_code=200,
                    json=lambda: {"result": [None], "error": None},
                )
            return MagicMock(
                status_code=200,
                json=lambda: {"result": [42], "error": None},
            )

        mock_post.side_effect = side_effect

        result = adapter.export(sample_sentences)

        assert "added" in result
        assert "duplicates" in result
        assert "errors" in result
        assert result["added"] == 1


def test_export_empty_sentences_raises(adapter):
    """Should raise ValueError for empty sentence list."""
    with pytest.raises(ValueError, match="No sentences"):
        adapter.export([])
