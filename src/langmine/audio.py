"""Audio downloading and clipping using yt-dlp and ffmpeg."""

import os
import subprocess
from pathlib import Path


def download_audio(
    video_id_or_url: str,
    output_dir: str,
) -> str:
    """Download the best audio from a YouTube video as MP3.

    Skips download if the file already exists (cached).

    Args:
        video_id_or_url: YouTube video ID or full URL.
        output_dir: Directory to save the MP3 file.

    Returns:
        Absolute path to the downloaded MP3 file.
    """
    from langmine.transcript import _extract_video_id

    video_id = _extract_video_id(video_id_or_url)
    output_path = Path(output_dir) / f"{video_id}.mp3"

    if output_path.exists():
        return str(output_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    url = f"https://www.youtube.com/watch?v={video_id}"
    result = subprocess.run(
        [
            "yt-dlp",
            "-x",
            "--audio-format", "mp3",
            "--audio-quality", "0",
            "--no-playlist",
            "--no-warnings",
            "-o", str(output_path.with_suffix(".%(ext)s")),
            url,
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to download audio for {video_id}: {result.stderr}"
        )

    # yt-dlp appends the extension, so the actual file is video_id.mp3
    actual_path = str(output_path)
    if not os.path.exists(actual_path):
        raise RuntimeError(
            f"Audio download appeared to succeed but file not found: {actual_path}"
        )

    return actual_path


def clip_audio(
    audio_path: str,
    start_ms: float,
    end_ms: float,
    pad_before_ms: int,
    pad_after_ms: int,
    output_dir: str,
    sentence_id: int | str,
) -> str:
    """Extract a segment of an audio file with padding.

    Args:
        audio_path: Path to the source audio file (MP3).
        start_ms: Start time of the sentence in milliseconds.
        end_ms: End time of the sentence in milliseconds.
        pad_before_ms: Additional padding before the sentence start.
        pad_after_ms: Additional padding after the sentence end.
        output_dir: Directory to save the clipped audio.
        sentence_id: Identifier for the output filename.

    Returns:
        Absolute path to the clipped audio file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Apply padding, clamping to 0
    clip_start_sec = max(0, (start_ms - pad_before_ms) / 1000.0)
    clip_end_sec = (end_ms + pad_after_ms) / 1000.0
    duration_sec = clip_end_sec - clip_start_sec

    # Zero-pad sentence ID for file ordering
    padded_id = str(sentence_id).zfill(4)
    output_path = output_dir / f"sentence_{padded_id}.mp3"

    result = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-ss", str(clip_start_sec),
            "-i", audio_path,
            "-t", str(duration_sec),
            "-acodec", "libmp3lame",
            "-q:a", "2",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to clip audio: {result.stderr}"
        )

    return str(output_path)
