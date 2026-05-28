"""Audio downloading and clipping using yt-dlp and ffmpeg.

Uses project-bundled ffmpeg/ffprobe binaries from ../../bin/ so tests
work even when the system ffmpeg gets wiped by container resets.
"""

import os
import subprocess
from pathlib import Path

# Project-bundled binaries — survive Docker container resets
# bin/ is a local setup artifact (gitignored), downloaded once via setup
_PROJECT_BIN = Path(__file__).parent.parent.parent / "bin"
_FFMPEG = str(_PROJECT_BIN / "ffmpeg") if (_PROJECT_BIN / "ffmpeg").exists() else "ffmpeg"
_FFPROBE = str(_PROJECT_BIN / "ffprobe") if (_PROJECT_BIN / "ffprobe").exists() else "ffprobe"


def _ffmpeg_location_args() -> list[str]:
    """Return --ffmpeg-location args for yt-dlp if using project binaries."""
    if _FFMPEG != "ffmpeg":
        return ["--ffmpeg-location", str(_PROJECT_BIN)]
    return []


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
            *_ffmpeg_location_args(),
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
            _FFMPEG,
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


def capture_frame(
    video_id_or_url: str,
    timestamp_ms: float,
    output_dir: str,
    sentence_id: int | str,
) -> str | None:
    """Capture a video frame at a specific timestamp as a JPEG screenshot.

    Downloads a short video segment around the timestamp, then extracts
    one frame. Falls back gracefully — returns None if yt-dlp or ffmpeg
    fail (e.g. no network, geo-restricted video).

    Args:
        video_id_or_url: YouTube video ID or full URL.
        timestamp_ms: Timestamp in milliseconds.
        output_dir: Directory to save the JPEG.
        sentence_id: Identifier for the output filename.

    Returns:
        Absolute path to the JPEG file, or None on failure.
    """
    import tempfile
    from langmine.transcript import _extract_video_id

    video_id = _extract_video_id(video_id_or_url)

    # Check cache first
    padded_id = str(sentence_id).zfill(4)
    output_path = Path(output_dir) / f"frame_{padded_id}.jpg"
    if output_path.exists():
        return str(output_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    timestamp_sec = timestamp_ms / 1000.0
    segment_start = max(0, timestamp_sec - 1.0)
    segment_end = timestamp_sec + 1.0

    url = f"https://www.youtube.com/watch?v={video_id}"

    with tempfile.TemporaryDirectory() as tmpdir:
        segment_path = Path(tmpdir) / f"segment_{padded_id}.mp4"

        dl_result = subprocess.run(
            [
                "yt-dlp",
                "--download-sections",
                f"*{segment_start:.1f}-{segment_end:.1f}",
                "-f", "best[height<=480]",
                "--recode-video", "mp4",
                "--no-playlist",
                "--no-warnings",
                "-o", str(segment_path),
                *_ffmpeg_location_args(),
                url,
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )

        if dl_result.returncode != 0 or not segment_path.exists():
            return None

        frame_time = min(1.0, (timestamp_sec - segment_start))
        ffmpeg_result = subprocess.run(
            [
                _FFMPEG,
                "-y",
                "-ss", str(frame_time),
                "-i", str(segment_path),
                "-frames:v", "1",
                "-q:v", "3",
                str(output_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if ffmpeg_result.returncode != 0 or not output_path.exists():
            return None

    return str(output_path)
