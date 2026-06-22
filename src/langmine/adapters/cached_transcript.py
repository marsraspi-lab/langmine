"""TranscriptSource that returns pre-cached transcript chunks.

Used for re-mining videos without re-downloading from YouTube.
Supports both source and target (translation) transcript caches.
"""

from langmine.domain.ports import SubtitleInfo, TranscriptChunk, TranscriptSource


class CachedTranscriptSource(TranscriptSource):
    """Returns transcript chunks from pre-loaded lists (no network).

    Holds both source-language chunks and optional target-language
    (translation subtitle) chunks.  ``fetch()`` returns the appropriate
    list based on the *language* parameter; ``list_subtitles()`` returns
    ``SubtitleInfo`` entries for whichever sets are present.

    Used for re-mining videos without re-downloading from YouTube.
    """

    def __init__(
        self,
        chunks: list[TranscriptChunk],
        *,
        source_language: str = "",
        source_kind: str = "",
        target_chunks: list[TranscriptChunk] | None = None,
        target_language: str = "",
        target_kind: str = "",
    ):
        self._chunks = chunks
        self._source_language = source_language
        self._source_kind = source_kind
        self._target_chunks = target_chunks or []
        self._target_language = target_language
        self._target_kind = target_kind

    def fetch(self, video_id: str, language: str = "") -> list[TranscriptChunk]:
        """Return cached chunks for *language*, falling back to source chunks."""
        if language and self._target_language and self._target_chunks:
            if language == self._target_language:
                return list(self._target_chunks)
        return list(self._chunks)

    def list_subtitles(self, video_id: str) -> list[SubtitleInfo]:
        """Return subtitle-info entries for available cached tracks."""
        subs: list[SubtitleInfo] = []
        if self._source_language:
            subs.append(
                SubtitleInfo(
                    language_code=self._source_language,
                    language_name=self._source_language,
                    kind=self._source_kind,
                )
            )
        if self._target_language and self._target_chunks:
            subs.append(
                SubtitleInfo(
                    language_code=self._target_language,
                    language_name=self._target_language,
                    kind=self._target_kind,
                )
            )
        return subs
