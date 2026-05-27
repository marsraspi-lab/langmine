"""YouTube Transcript adapter — wraps transcript.py behind TranscriptSource port."""

from langmine.domain.ports import TranscriptSource, TranscriptChunk
from langmine.transcript import fetch_transcript


class YouTubeTranscriptAdapter(TranscriptSource):
    """Fetches subtitles from YouTube via youtube-transcript-api."""

    def fetch(self, video_id: str) -> list[TranscriptChunk]:
        chunks = fetch_transcript(video_id)
        return [
            TranscriptChunk(
                text=c.text,
                start_ms=c.start_ms,
                duration_ms=c.duration_ms,
            )
            for c in chunks
        ]
