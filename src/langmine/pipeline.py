"""End-to-end sentence mining pipeline."""

from langmine.transcript import fetch_transcript, merge_sentences
from langmine.audio import download_audio, clip_audio
from langmine.config import load_config


def extract_one_sentence(
    video_url: str,
    output_dir: str,
    gap_ms: int | None = None,
    pad_before_ms: int | None = None,
    pad_after_ms: int | None = None,
) -> dict:
    """End-to-end: extract the first sentence from a YouTube video.

    Downloads the full audio, fetches subtitles, merges chunks into
    sentences, extracts the first sentence's audio clip.

    Args:
        video_url: YouTube URL or video ID.
        output_dir: Directory for audio downloads and clips.
        gap_ms: Max gap between subtitle chunks for merging (default from config).
        pad_before_ms: Audio padding before sentence start (default from config).
        pad_after_ms: Audio padding after sentence end (default from config).

    Returns:
        Dict with keys: text, start_ms, end_ms, audio_path.
    """
    config = load_config()

    if gap_ms is None:
        gap_ms = config.sentence_gap_ms
    if pad_before_ms is None:
        pad_before_ms = config.audio_pad_before_ms
    if pad_after_ms is None:
        pad_after_ms = config.audio_pad_after_ms

    # 1. Fetch transcript and merge into sentences
    chunks = fetch_transcript(video_url)
    sentences = merge_sentences(chunks, gap_ms=gap_ms)

    if not sentences:
        raise ValueError("No sentences could be extracted from the video.")

    first = sentences[0]

    # 2. Download full audio
    audio_path = download_audio(video_url, output_dir=output_dir)

    # 3. Clip the first sentence
    clip_dir = f"{output_dir}/clips"
    clip_path = clip_audio(
        audio_path=audio_path,
        start_ms=first.start_ms,
        end_ms=first.end_ms,
        pad_before_ms=pad_before_ms,
        pad_after_ms=pad_after_ms,
        output_dir=clip_dir,
        sentence_id=1,
    )

    return {
        "text": first.text,
        "start_ms": first.start_ms,
        "end_ms": first.end_ms,
        "audio_path": clip_path,
    }
