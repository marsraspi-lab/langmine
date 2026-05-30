"""Transcript fetching and sentence merging for YouTube videos."""

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound, VideoUnavailable

from langmine.domain.ports import TranscriptChunk, MergedSentence


def fetch_transcript(video_id_or_url: str, user_agent: str = "") -> list[TranscriptChunk]:
    """Fetch subtitle chunks for a YouTube video.

    Args:
        video_id_or_url: YouTube video ID (11 chars) or full URL.
        user_agent: Optional custom User-Agent header. If empty, uses
            youtube-transcript-api's default.

    Returns:
        List of transcript chunks with text and timing.

    Raises:
        ValueError: If the video ID is invalid or transcript unavailable.
    """
    video_id = _extract_video_id(video_id_or_url)

    kwargs = {}
    if user_agent:
        import requests as _requests
        session = _requests.Session()
        session.headers.update({"User-Agent": user_agent})
        kwargs["http_client"] = session

    try:
        api = YouTubeTranscriptApi(**kwargs)
        transcript = api.fetch(video_id)
    except (TranscriptsDisabled, NoTranscriptFound) as e:
        raise ValueError(
            f"No transcript available for video '{video_id}'. "
            f"The video may not have subtitles or they may be disabled."
        ) from e
    except VideoUnavailable as e:
        raise ValueError(
            f"Video '{video_id}' is unavailable or private."
        ) from e

    return [
        TranscriptChunk(
            text=entry.text,
            start_ms=entry.start * 1000,
            duration_ms=entry.duration * 1000,
        )
        for entry in transcript
    ]


def merge_sentences(
    chunks: list[TranscriptChunk], gap_ms: int = 500
) -> list[MergedSentence]:
    """Merge subtitle chunks into sentences using a pause-based heuristic.

    Adjacent chunks are merged if the time gap between them is ≤ gap_ms.
    A gap is the difference between (chunk_A.start + chunk_A.duration)
    and chunk_B.start.

    Args:
        chunks: Chronologically ordered subtitle chunks.
        gap_ms: Maximum gap in milliseconds between chunks to merge.

    Returns:
        List of merged sentences with text and timing boundaries.
    """
    if not chunks:
        return []

    sentences: list[MergedSentence] = []
    current_text = chunks[0].text.strip()
    current_start = chunks[0].start_ms
    current_end = chunks[0].start_ms + chunks[0].duration_ms

    for i in range(1, len(chunks)):
        prev_end = current_end
        next_start = chunks[i].start_ms
        gap = next_start - prev_end

        if gap <= gap_ms:
            # Merge: append text with a space
            current_text += " " + chunks[i].text.strip()
            current_end = chunks[i].start_ms + chunks[i].duration_ms
        else:
            # Split: finish current sentence, start new one
            sentences.append(
                MergedSentence(
                    text=current_text,
                    start_ms=current_start,
                    end_ms=current_end,
                )
            )
            current_text = chunks[i].text.strip()
            current_start = chunks[i].start_ms
            current_end = chunks[i].start_ms + chunks[i].duration_ms

    # Don't forget the last sentence
    sentences.append(
        MergedSentence(
            text=current_text,
            start_ms=current_start,
            end_ms=current_end,
        )
    )

    return sentences


def _extract_video_id(url_or_id: str) -> str:
    """Extract an 11-character YouTube video ID from a URL or raw ID."""
    import re

    # Already a raw video ID (11 alphanumeric + _- chars)
    if re.match(r"^[A-Za-z0-9_-]{11}$", url_or_id):
        return url_or_id

    # Try common URL patterns
    patterns = [
        r"youtube\.com/watch\?v=([A-Za-z0-9_-]{11})",
        r"youtu\.be/([A-Za-z0-9_-]{11})",
        r"youtube\.com/embed/([A-Za-z0-9_-]{11})",
        r"youtube\.com/shorts/([A-Za-z0-9_-]{11})",
        r"m\.youtube\.com/watch\?v=([A-Za-z0-9_-]{11})",
    ]

    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)

    raise ValueError(
        f"Could not extract a YouTube video ID from '{url_or_id}'. "
        f"Provide a full URL or an 11-character video ID."
    )
