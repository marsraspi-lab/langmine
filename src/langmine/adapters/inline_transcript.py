"""Inline transcript adapter — holds pre-loaded chunks from an uploaded file.

Used as a fallback when youtube-transcript-api is IP-blocked.
The user downloads subtitles from their browser and uploads them.
"""

from langmine.domain.ports import SubtitleInfo, TranscriptChunk, TranscriptSource


class InlineTranscriptSource(TranscriptSource):
    """Transcript source backed by pre-loaded chunks (from file upload)."""

    def __init__(self, chunks: list[TranscriptChunk]):
        self._chunks = chunks

    def fetch(self, video_id: str, language: str = "") -> list[TranscriptChunk]:
        # video_id and language are ignored — we already have the chunks
        return self._chunks

    def list_subtitles(self, video_id: str) -> list[SubtitleInfo]:
        return []  # Uploaded files have no subtitle tracks to list
