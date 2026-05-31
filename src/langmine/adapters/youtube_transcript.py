"""YouTube Transcript adapter — wraps transcript.py behind TranscriptSource port."""

from langmine.domain.ports import TranscriptSource, TranscriptChunk
from langmine.transcript import fetch_transcript


class YouTubeTranscriptAdapter(TranscriptSource):
    """Fetches subtitles from YouTube via youtube-transcript-api."""

    def __init__(self, user_agent: str = "", language_codes: list[str] | None = None):
        self._user_agent = user_agent
        self._language_codes = language_codes or []

    def fetch(self, video_id: str) -> list[TranscriptChunk]:
        return fetch_transcript(video_id, user_agent=self._user_agent,
                                language_codes=self._language_codes)
