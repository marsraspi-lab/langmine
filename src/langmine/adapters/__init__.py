"""Adapters: concrete implementations of domain ports.

Each adapter wraps an external system behind a port interface.
"""

from langmine.adapters.youtube_transcript import YouTubeTranscriptAdapter
from langmine.adapters.ytdlp_audio import YtdlpAudioAdapter
from langmine.adapters.sqlite_persistence import SQLitePersistence
from langmine.adapters.google_translate import GoogleTranslateAdapter
from langmine.adapters.cc_cedict import CcCedictAdapter
from langmine.adapters.jieba_frequency import JiebaFrequencyAdapter
from langmine.adapters.subtlex_ch import SubtlexChAdapter

__all__ = [
    "YouTubeTranscriptAdapter",
    "YtdlpAudioAdapter",
    "SQLitePersistence",
    "GoogleTranslateAdapter",
    "CcCedictAdapter",
    "JiebaFrequencyAdapter",
    "SubtlexChAdapter",
]
