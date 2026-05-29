"""YouTube Transcript adapter — wraps transcript.py behind TranscriptSource port."""

from langmine.domain.ports import TranscriptSource, TranscriptChunk
from langmine.transcript import fetch_transcript


class YouTubeTranscriptAdapter(TranscriptSource):
    """Fetches subtitles from YouTube via youtube-transcript-api."""

    def __init__(self, user_agent: str = ""):
        self._user_agent = user_agent

    def fetch(self, video_id: str) -> list[TranscriptChunk]:
        return fetch_transcript(video_id, user_agent=self._user_agent)
