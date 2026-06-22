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


def test_cached_transcript_ignores_language_when_no_target():
    """When no target chunks are provided, fetch returns source chunks regardless of language."""
    chunks = [TranscriptChunk(text="test", start_ms=0, duration_ms=500)]
    source = CachedTranscriptSource(chunks)
    result = source.fetch("any_video_id", language="zh-Hans")
    assert result == chunks


def test_cached_transcript_list_subtitles_returns_empty():
    """CachedTranscriptSource.list_subtitles should return an empty list."""
    source = CachedTranscriptSource([])
    subs = source.list_subtitles("any_video_id")
    assert subs == []


def test_cached_transcript_returns_target_chunks_for_matching_language():
    """When target chunks are provided, fetch returns them when language matches."""
    source_chunks = [TranscriptChunk(text="你好", start_ms=0, duration_ms=1000)]
    target_chunks = [TranscriptChunk(text="Hallo", start_ms=0, duration_ms=1000)]
    source = CachedTranscriptSource(
        source_chunks,
        source_language="zh-Hans",
        source_kind="manual",
        target_chunks=target_chunks,
        target_language="de",
        target_kind="manual",
    )
    # Request target language — should get target chunks
    result = source.fetch("video_id", language="de")
    assert len(result) == 1
    assert result[0].text == "Hallo"


def test_cached_transcript_falls_back_to_source_for_unknown_language():
    """When language doesn't match target, fetch falls back to source chunks."""
    source_chunks = [TranscriptChunk(text="你好", start_ms=0, duration_ms=1000)]
    target_chunks = [TranscriptChunk(text="Hallo", start_ms=0, duration_ms=1000)]
    source = CachedTranscriptSource(
        source_chunks,
        target_chunks=target_chunks,
        target_language="de",
    )
    # Request a language we don't have cached
    result = source.fetch("video_id", language="fr")
    assert result[0].text == "你好"  # Falls back to source


def test_cached_transcript_list_subtitles_with_metadata():
    """When source/target metadata is provided, list_subtitles returns proper entries."""
    source = CachedTranscriptSource(
        [TranscriptChunk(text="你好", start_ms=0, duration_ms=1000)],
        source_language="zh-Hans",
        source_kind="manual",
        target_chunks=[TranscriptChunk(text="Hallo", start_ms=0, duration_ms=1000)],
        target_language="de",
        target_kind="manual",
    )
    subs = source.list_subtitles("video_id")
    assert len(subs) == 2
    assert subs[0].language_code == "zh-Hans"
    assert subs[0].kind == "manual"
    assert subs[1].language_code == "de"
    assert subs[1].kind == "manual"


def test_cached_transcript_empty_chunks():
    """CachedTranscriptSource with empty chunks should return empty list."""
    source = CachedTranscriptSource([])
    result = source.fetch("any_video_id", language="")
    assert result == []
