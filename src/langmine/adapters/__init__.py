"""Adapters: concrete implementations of domain ports.

Each adapter wraps an external system behind a port interface.
"""

from langmine.adapters.youtube_transcript import YouTubeTranscriptAdapter
from langmine.adapters.ytdlp_audio import YtdlpAudioAdapter
from langmine.adapters.sqlite_persistence import SQLitePersistence

__all__ = [
    "YouTubeTranscriptAdapter",
    "YtdlpAudioAdapter",
    "SQLitePersistence",
]
