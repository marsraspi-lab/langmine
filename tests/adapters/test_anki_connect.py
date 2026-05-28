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


def test_snapshot_note_payload(adapter, sample_sentences):
    """Golden test: verify exact note fields sent to AnkiConnect.

    Any change to note fields or model structure breaks this test
    intentionally — it's a regression guard.
    """
    import json

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
        adapter.export(sample_sentences)

        # Extract the addNotes payload
        add_notes_call = [
            c for c in mock_post.call_args_list
            if c[1]["json"]["action"] == "addNotes"
        ][0]
        payload = add_notes_call[1]["json"]
        notes = payload["params"]["notes"]

        assert len(notes) == 1
        note = notes[0]

        # Verify all expected fields
        assert note["deckName"] == "Chinese::Sentence Mining"
        assert note["modelName"] == "LangMine Sentence"
        assert note["tags"] == ["langmine"]

        fields = note["fields"]
        assert fields["sentence_zh"] == "你好"
        assert fields["sentence_pinyin"] == "nǐ hǎo"
        assert fields["translation_de"] == "Hallo"
        assert fields["unknown_word"] == "你好"
        assert fields["audio"] == ""  # No audio attached

        # Verify no extra fields (schema drift)
        assert set(fields.keys()) == {
            "sentence_zh", "sentence_pinyin", "translation_de",
            "unknown_word", "audio",
        }


def test_snapshot_note_payload_with_audio(adapter):
    """Snapshot test: note with audio includes [sound:...] in audio field."""
    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = os.path.join(tmpdir, "clip.mp3")
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
            adapter.export(sentences)

            add_notes_call = [
                c for c in mock_post.call_args_list
                if c[1]["json"]["action"] == "addNotes"
            ][0]
            fields = add_notes_call[1]["json"]["params"]["notes"][0]["fields"]

            assert fields["audio"].startswith("[sound:")
            assert "clip.mp3" in fields["audio"]
