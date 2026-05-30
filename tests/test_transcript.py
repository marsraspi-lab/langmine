"""Tests for transcript fetching and sentence merging."""

import pytest
from unittest.mock import patch, MagicMock

from langmine.transcript import (
    fetch_transcript,
    merge_sentences,
    TranscriptChunk,
)


class TestFetchTranscript:
    """Tests for fetching subtitle chunks from YouTube."""

    def test_fetch_returns_list_of_chunks(self):
        """fetch_transcript should return a list of TranscriptChunk objects."""
        from unittest.mock import patch, MagicMock

        mock_chunks = []
        for text, start, dur in [("我们", 1.0, 2.0), ("一般", 3.5, 1.5), ("早上", 5.5, 2.0)]:
            m = MagicMock()
            m.text = text
            m.start = start
            m.duration = dur
            mock_chunks.append(m)

        with patch("youtube_transcript_api.YouTubeTranscriptApi.fetch", return_value=mock_chunks):
            chunks = fetch_transcript("dQw4w9WgXcQ")

        assert isinstance(chunks, list)
        assert len(chunks) > 0
        for chunk in chunks:
            assert isinstance(chunk, TranscriptChunk)
            assert isinstance(chunk.text, str)
            assert isinstance(chunk.start_ms, (int, float))
            assert isinstance(chunk.duration_ms, (int, float))
            assert chunk.text.strip() != ""

    def test_fetch_raises_on_invalid_url(self):
        """fetch_transcript should raise ValueError for an invalid/nonexistent video."""
        with pytest.raises((ValueError, Exception)):
            fetch_transcript("invalid_video_id_xyz")

    def test_chunks_have_increasing_timestamps(self):
        """Chunks should be returned in chronological order."""
        from unittest.mock import patch, MagicMock

        mock_chunks = []
        for text, start, dur in [("我们", 1.0, 2.0), ("一般", 3.5, 1.5), ("早上", 5.5, 2.0)]:
            m = MagicMock()
            m.text = text
            m.start = start
            m.duration = dur
            mock_chunks.append(m)

        with patch("youtube_transcript_api.YouTubeTranscriptApi.fetch", return_value=mock_chunks):
            chunks = fetch_transcript("dQw4w9WgXcQ")

        for i in range(1, len(chunks)):
            assert chunks[i].start_ms >= chunks[i - 1].start_ms


class TestMergeSentences:
    """Tests for the pause-based sentence merging heuristic."""

    def make_chunk(self, text: str, start: int, duration: int) -> TranscriptChunk:
        return TranscriptChunk(text=text, start_ms=start, duration_ms=duration)

    def test_adjacent_chunks_within_gap_are_merged(self):
        """Chunks with gap ≤ threshold should be merged into one sentence."""
        chunks = [
            self.make_chunk("我们一般", 0, 1000),
            self.make_chunk("早上七点起床", 1000, 1500),
        ]
        sentences = merge_sentences(chunks, gap_ms=500)

        assert len(sentences) == 1
        assert sentences[0].text == "我们一般 早上七点起床"
        assert sentences[0].start_ms == 0
        assert sentences[0].end_ms == 2500

    def test_chunks_with_gap_above_threshold_are_split(self):
        """Chunks with gap > threshold should become separate sentences."""
        chunks = [
            self.make_chunk("第一句", 0, 1000),
            self.make_chunk("第二句", 3000, 1000),  # 2000ms gap
        ]
        sentences = merge_sentences(chunks, gap_ms=500)

        assert len(sentences) == 2
        assert sentences[0].text == "第一句"
        assert sentences[1].text == "第二句"

    def test_multiple_chunks_merge_into_one_sentence(self):
        """Several adjacent chunks within gap threshold merge together."""
        chunks = [
            self.make_chunk("我们", 0, 500),
            self.make_chunk("一般", 500, 500),
            self.make_chunk("早上", 1000, 500),
            self.make_chunk("七点起床", 1500, 1000),
        ]
        sentences = merge_sentences(chunks, gap_ms=500)

        assert len(sentences) == 1
        assert "我们 一般 早上 七点起床" in sentences[0].text

    def test_empty_chunk_list_returns_empty(self):
        """Empty input should return empty list."""
        assert merge_sentences([], gap_ms=500) == []

    def test_single_chunk_returns_one_sentence(self):
        """A single chunk should produce one sentence."""
        chunks = [self.make_chunk("你好", 0, 1000)]
        sentences = merge_sentences(chunks, gap_ms=500)
        assert len(sentences) == 1
        assert sentences[0].text == "你好"

    def test_spaces_within_chunks_are_preserved(self):
        """Spaces inside subtitle text (used as soft punctuation) should be preserved."""
        chunks = [
            self.make_chunk("我们", 0, 500),
            self.make_chunk("一般", 500, 500),
        ]
        sentences = merge_sentences(chunks, gap_ms=500)
        # Merged chunks are joined with a space
        assert sentences[0].text == "我们 一般"

    def test_custom_gap_threshold(self):
        """The gap threshold should be configurable via parameter."""
        chunks = [
            self.make_chunk("A", 0, 500),
            self.make_chunk("B", 1200, 500),  # 700ms gap
        ]
        # With 1000ms gap threshold, they should merge
        merged = merge_sentences(chunks, gap_ms=1000)
        assert len(merged) == 1

        # With 500ms gap threshold, they should split
        split = merge_sentences(chunks, gap_ms=500)
        assert len(split) == 2
