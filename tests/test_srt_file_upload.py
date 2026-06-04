"""Tests for SRT file upload sentence merging behavior.

Verifies that gap_ms=0 (file upload) keeps each subtitle entry as its
own sentence, while gap_ms=500 (YouTube) merges entries with tight gaps.
"""

from langmine.domain.ports import TranscriptChunk
from langmine.transcript import merge_sentences
from langmine.transcript_parser import parse_subtitle_file


def _load_sample_srt() -> list[TranscriptChunk]:
    """Parse the sample SRT fixture and return transcript chunks."""
    import os

    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "sample.srt")
    with open(fixture_path) as f:
        content = f.read()
    return parse_subtitle_file(content, filename="sample.srt")


class TestSrtFileUploadMerging:
    """Verify that gap-based merging behaves correctly for SRT files."""

    def test_parse_srt_produces_five_chunks(self):
        """Sample SRT should parse to exactly 5 subtitle chunks."""
        chunks = _load_sample_srt()
        assert len(chunks) == 5

    def test_each_chunk_is_full_sentence(self):
        """Each SRT entry should contain a complete Chinese sentence."""
        chunks = _load_sample_srt()
        assert all("\n" not in c.text for c in chunks), (
            "chunks should not contain newlines"
        )
        assert all(len(c.text) >= 3 for c in chunks), (
            "each chunk should have meaningful text"
        )

    def test_gap_ms_zero_keeps_all_separate(self):
        """With gap_ms=0, each SRT entry is its own sentence (no merging)."""
        chunks = _load_sample_srt()
        sentences = merge_sentences(chunks, gap_ms=0)
        assert len(sentences) == 5, (
            f"Expected 5 sentences with gap_ms=0, got {len(sentences)}"
        )

    def test_gap_ms_500_merges_tight_entries(self):
        """With gap_ms=500, entries with ≤500ms gaps are merged.

        The sample SRT has exactly 500ms gaps between all entries,
        so all 5 should merge into 1 sentence.
        """
        chunks = _load_sample_srt()
        sentences = merge_sentences(chunks, gap_ms=500)
        assert len(sentences) == 1, (
            f"Expected 1 merged sentence with gap_ms=500, got {len(sentences)}"
        )
        # The merged text should contain all 5 original entries
        for chunk in chunks:
            assert chunk.text.strip() in sentences[0].text

    def test_merge_preserves_timing_boundaries(self):
        """Merged sentence should span from first entry start to last entry end."""
        chunks = _load_sample_srt()
        sentences = merge_sentences(chunks, gap_ms=500)
        assert sentences[0].start_ms == chunks[0].start_ms
        assert sentences[0].end_ms == chunks[-1].start_ms + chunks[-1].duration_ms
