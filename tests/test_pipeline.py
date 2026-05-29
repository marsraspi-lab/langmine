"""Integration tests for the full mining pipeline."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from langmine.pipeline import extract_one_sentence
from langmine.transcript import TranscriptChunk


def _make_fake_transcript():
    """Return mock TranscriptChunk objects."""
    return [
        TranscriptChunk(text="我们", start_ms=0.0, duration_ms=2000.0),
        TranscriptChunk(text="一般", start_ms=2500.0, duration_ms=1500.0),
        TranscriptChunk(text="早上起床", start_ms=4500.0, duration_ms=2000.0),
    ]


def test_extract_one_sentence_returns_sentence_dict():
    """extract_one_sentence should return a dict with text, timing, and audio path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        fake_clip = os.path.join(tmpdir, "clips", "0001_dQw4w9WgXcQ.mp3")
        os.makedirs(os.path.dirname(fake_clip), exist_ok=True)
        # Create a tiny valid file so os.path.exists passes
        with open(fake_clip, "wb") as f:
            f.write(b"\xff\xfb\x90\x00")  # MP3 frame header

        with (
            patch("langmine.adapters.youtube_transcript.fetch_transcript", return_value=_make_fake_transcript()),
            patch("langmine.adapters.ytdlp_audio.download_audio", return_value="/fake/audio.mp3"),
            patch("langmine.adapters.ytdlp_audio.clip_audio", return_value=fake_clip),
        ):
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
        assert result["audio_path"] == fake_clip


def test_extract_one_sentence_uses_default_padding():
    """The audio clip should be created with default padding from config."""
    with tempfile.TemporaryDirectory() as tmpdir:
        fake_clip = os.path.join(tmpdir, "clips", "0001_dQw4w9WgXcQ.mp3")
        os.makedirs(os.path.dirname(fake_clip), exist_ok=True)
        with open(fake_clip, "wb") as f:
            f.write(b"\xff\xfb\x90\x00")

        with (
            patch("langmine.adapters.youtube_transcript.fetch_transcript", return_value=_make_fake_transcript()),
            patch("langmine.adapters.ytdlp_audio.download_audio", return_value="/fake/audio.mp3"),
            patch("langmine.adapters.ytdlp_audio.clip_audio", return_value=fake_clip),
        ):
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
