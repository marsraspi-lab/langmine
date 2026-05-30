"""Adapters: concrete implementations of domain ports.

Each adapter wraps an external system behind a port interface.
Language-specific adapters live under languages/<lang>/.
"""

from langmine.adapters.youtube_transcript import YouTubeTranscriptAdapter
from langmine.adapters.inline_transcript import InlineTranscriptSource
from langmine.adapters.ytdlp_audio import YtdlpAudioAdapter
from langmine.adapters.sqlite_persistence import SQLitePersistence
from langmine.adapters.google_translate import GoogleTranslateAdapter
from langmine.adapters.google_image_search import GoogleImageSearch
from langmine.adapters.anki_connect import AnkiConnectAdapter

__all__ = [
    "YouTubeTranscriptAdapter",
    "InlineTranscriptSource",
    "YtdlpAudioAdapter",
    "SQLitePersistence",
    "GoogleTranslateAdapter",
    "GoogleImageSearch",
    "AnkiConnectAdapter",
]
