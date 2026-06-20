"""TranscriptSource that returns pre-cached transcript chunks.

Used for re-mining videos without re-downloading from YouTube.
"""

from langmine.domain.ports import SubtitleInfo, TranscriptChunk, TranscriptSource


class CachedTranscriptSource(TranscriptSource):
    """Returns transcript chunks from a pre-loaded list (no network).

    Used for re-mining videos without re-downloading from YouTube.
    """

    def __init__(self, chunks: list[TranscriptChunk]):
        self._chunks = chunks

    def fetch(self, video_id: str, language: str = "") -> list[TranscriptChunk]:
        return list(self._chunks)

    def list_subtitles(self, video_id: str) -> list[SubtitleInfo]:
        return []
