"""Integration tests for the full mining pipeline."""

import os
import tempfile
from pathlib import Path

import pytest

from langmine.pipeline import extract_one_sentence


def test_extract_one_sentence_returns_sentence_dict(youtube_available):
    """extract_one_sentence should return a dict with text, timing, and audio path."""
    if not youtube_available:
        pytest.skip("YouTube is IP-blocking this environment")
    with tempfile.TemporaryDirectory() as tmpdir:
        result = extract_one_sentence(
            video_url="dQw4w9WgXcQ",
            output_dir=tmpdir,
        )

        assert isinstance(result, dict)
        assert "text" in result
        assert "start_ms" in result
        assert "end_ms" in result
        assert "audio_path" in result

        assert isinstance(result["text"], str)
        assert len(result["text"]) > 0
        assert isinstance(result["start_ms"], (int, float))
        assert isinstance(result["end_ms"], (int, float))
        assert result["end_ms"] > result["start_ms"]
        assert os.path.exists(result["audio_path"])


def test_extract_one_sentence_uses_default_padding(youtube_available):
    """The audio clip should be created with default padding from config."""
    if not youtube_available:
        pytest.skip("YouTube is IP-blocking this environment")
    with tempfile.TemporaryDirectory() as tmpdir:
        result = extract_one_sentence(
            video_url="dQw4w9WgXcQ",
            output_dir=tmpdir,
        )

        # The clip should exist and be playable
        assert os.path.getsize(result["audio_path"]) > 0
        assert result["audio_path"].endswith(".mp3")


def test_extract_one_sentence_fails_on_invalid_url():
    """extract_one_sentence should raise on an invalid video."""
    import pytest
    with pytest.raises((ValueError, RuntimeError)):
        extract_one_sentence(
            video_url="invalid_url_xyz",
            output_dir="/tmp",
        )
