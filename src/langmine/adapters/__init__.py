"""Adapters package — concrete implementations of every domain port.

Each adapter wraps one external system (YouTube, SQLite, AnkiConnect, etc.)
behind a port interface from domain.ports. Language-specific adapters
(dictionary, frequency) live under languages/<lang>/, not here.

Re-exports all adapter classes for convenient single-import wiring.
"""

from langmine.adapters.anki_connect import AnkiConnectAdapter
from langmine.adapters.google_image_search import GoogleImageSearch
from langmine.adapters.google_translate import GoogleTranslateAdapter
from langmine.adapters.inline_transcript import InlineTranscriptSource
from langmine.adapters.sqlite_persistence import SQLitePersistence
from langmine.adapters.youtube_transcript import YouTubeTranscriptAdapter
from langmine.adapters.ytdlp_audio import YtdlpAudioAdapter

__all__ = [
    "YouTubeTranscriptAdapter",
    "InlineTranscriptSource",
    "YtdlpAudioAdapter",
    "SQLitePersistence",
    "GoogleTranslateAdapter",
    "GoogleImageSearch",
    "AnkiConnectAdapter",
]
