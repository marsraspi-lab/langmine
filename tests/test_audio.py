"""Tests for audio downloading and clipping."""

import os
import tempfile
from pathlib import Path

import pytest

from langmine.audio import download_audio, clip_audio


# === Audio Download Tests ===


def test_download_audio_returns_path():
    """download_audio should return a path to an MP3 file that exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = download_audio(
            "dQw4w9WgXcQ",
            output_dir=tmpdir,
        )
        assert os.path.exists(path)
        assert path.endswith(".mp3")
        assert os.path.getsize(path) > 0


def test_download_audio_skips_if_already_cached():
    """If the file already exists, download_audio should return it immediately."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path1 = download_audio("dQw4w9WgXcQ", output_dir=tmpdir)
        mtime1 = os.path.getmtime(path1)

        path2 = download_audio("dQw4w9WgXcQ", output_dir=tmpdir)
        mtime2 = os.path.getmtime(path2)

        assert path1 == path2
        assert mtime1 == mtime2  # File not re-downloaded


def test_download_audio_named_by_video_id():
    """The output filename should include the video ID."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = download_audio("dQw4w9WgXcQ", output_dir=tmpdir)
        assert "dQw4w9WgXcQ" in str(path)


# === Audio Clip Tests ===


def _create_test_audio(dir_path: str) -> str:
    """Create a small test audio file using ffmpeg for clip tests."""
    audio_path = Path(dir_path) / "test.mp3"
    # Generate 5 seconds of silence
    os.system(
        f"ffmpeg -y -f lavfi -i anullsrc=r=44100:cl=mono "
        f"-t 5 -q:a 9 -acodec libmp3lame {audio_path} 2>/dev/null"
    )
    return str(audio_path)


def test_clip_audio_extracts_segment():
    """clip_audio should extract a segment and save it as a new file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = _create_test_audio(tmpdir)
        output_dir = Path(tmpdir) / "clips"
        output_dir.mkdir()

        clip_path = clip_audio(
            audio_path=audio_path,
            start_ms=1000,
            end_ms=3000,
            pad_before_ms=250,
            pad_after_ms=300,
            output_dir=str(output_dir),
            sentence_id=1,
        )

        assert os.path.exists(clip_path)
        assert clip_path.endswith(".mp3")
        assert os.path.getsize(clip_path) > 0


def test_clip_audio_applies_padding():
    """The clip should include the configured padding before and after."""
    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = _create_test_audio(tmpdir)
        output_dir = Path(tmpdir) / "clips"
        output_dir.mkdir()

        # With 1000ms padding, clip should be longer
        clip_padded = clip_audio(
            audio_path=audio_path,
            start_ms=1000,
            end_ms=2000,
            pad_before_ms=500,
            pad_after_ms=500,
            output_dir=str(output_dir),
            sentence_id="padded",
        )

        # With 0 padding, clip is exact
        clip_exact = clip_audio(
            audio_path=audio_path,
            start_ms=1000,
            end_ms=2000,
            pad_before_ms=0,
            pad_after_ms=0,
            output_dir=str(output_dir),
            sentence_id="exact",
        )

        # Padded clip should be larger (more audio data)
        padded_size = os.path.getsize(clip_padded)
        exact_size = os.path.getsize(clip_exact)
        assert padded_size > exact_size, (
            f"Padded clip ({padded_size} bytes) should be larger "
            f"than exact clip ({exact_size} bytes)"
        )


def test_clip_audio_clamps_to_start():
    """Padding should not go below 0ms (start of audio)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = _create_test_audio(tmpdir)
        output_dir = Path(tmpdir) / "clips"
        output_dir.mkdir()

        # Sentence at 500ms with 1000ms padding — should clamp to 0
        clip_path = clip_audio(
            audio_path=audio_path,
            start_ms=500,
            end_ms=1500,
            pad_before_ms=1000,
            pad_after_ms=300,
            output_dir=str(output_dir),
            sentence_id="clamped",
        )

        assert os.path.exists(clip_path)


def test_clip_audio_includes_sentence_id_in_filename():
    """The output filename should include the sentence ID."""
    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = _create_test_audio(tmpdir)
        output_dir = Path(tmpdir) / "clips"
        output_dir.mkdir()

        clip_path = clip_audio(
            audio_path=audio_path,
            start_ms=1000,
            end_ms=3000,
            pad_before_ms=250,
            pad_after_ms=300,
            output_dir=str(output_dir),
            sentence_id=42,
        )

        assert "42" in str(clip_path) or "042" in str(clip_path)
