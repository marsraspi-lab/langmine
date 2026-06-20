"""Tests for CachedTranscriptSource."""

from langmine.adapters.cached_transcript import CachedTranscriptSource
from langmine.domain.ports import TranscriptChunk


def test_cached_transcript_returns_stored_chunks():
    """CachedTranscriptSource should return the chunks it was created with."""
    chunks = [
        TranscriptChunk(text="你好", start_ms=0, duration_ms=1000),
        TranscriptChunk(text="世界", start_ms=2000, duration_ms=1500),
    ]
    source = CachedTranscriptSource(chunks)
    result = source.fetch("any_video_id", language="")
    assert len(result) == 2
    assert result[0].text == "你好"
    assert result[0].start_ms == 0
    assert result[0].duration_ms == 1000
    assert result[1].text == "世界"
    assert result[1].start_ms == 2000
    assert result[1].duration_ms == 1500


def test_cached_transcript_ignores_language_param():
    """CachedTranscriptSource.fetch should ignore the language parameter."""
    chunks = [TranscriptChunk(text="test", start_ms=0, duration_ms=500)]
    source = CachedTranscriptSource(chunks)
    result = source.fetch("any_video_id", language="zh-Hans")
    assert result == chunks


def test_cached_transcript_list_subtitles_returns_empty():
    """CachedTranscriptSource.list_subtitles should return an empty list."""
    source = CachedTranscriptSource([])
    subs = source.list_subtitles("any_video_id")
    assert subs == []


def test_cached_transcript_empty_chunks():
    """CachedTranscriptSource with empty chunks should return empty list."""
    source = CachedTranscriptSource([])
    result = source.fetch("any_video_id", language="")
    assert result == []
