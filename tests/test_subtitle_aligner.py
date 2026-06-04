"""Tests for subtitle_aligner.py — time-overlap alignment of target subtitles."""

from langmine.domain.models import Sentence
from langmine.domain.ports import TranscriptChunk
from langmine.subtitle_aligner import align_target_subtitles


def _make_sentence(start_ms, end_ms, text="test"):
    return Sentence(
        text=text,
        start_ms=start_ms,
        end_ms=end_ms,
        video_id=1,
        text_segmented=text,
    )


def _make_chunk(text, start_ms, duration_ms):
    return TranscriptChunk(text=text, start_ms=start_ms, duration_ms=duration_ms)


class TestAlignTargetSubtitles:
    def test_full_overlap_single_chunk(self):
        """A single target chunk fully overlapping the sentence window."""
        sentences = [_make_sentence(1000, 5000)]
        chunks = [_make_chunk("Hallo Welt", 1000, 4000)]
        align_target_subtitles(sentences, chunks)
        assert sentences[0].translation == "Hallo Welt"

    def test_partial_overlap(self):
        """Target chunk starts before sentence, ends within it."""
        sentences = [_make_sentence(2000, 5000)]
        chunks = [_make_chunk("teilweise", 1000, 1500)]  # 1000-2500
        align_target_subtitles(sentences, chunks)
        assert sentences[0].translation == "teilweise"

    def test_no_overlap_leaves_empty(self):
        """No overlapping chunks → translation stays empty."""
        sentences = [_make_sentence(1000, 2000)]
        chunks = [_make_chunk("später", 5000, 1000)]
        align_target_subtitles(sentences, chunks)
        assert sentences[0].translation == ""

    def test_multiple_overlapping_chunks(self):
        """Multiple target chunks overlap the sentence → concatenated."""
        sentences = [_make_sentence(1000, 5000)]
        chunks = [
            _make_chunk("Erster", 1000, 1500),
            _make_chunk("Satz.", 2800, 1500),
        ]
        align_target_subtitles(sentences, chunks)
        assert sentences[0].translation == "Erster Satz."

    def test_empty_target_chunks(self):
        """Empty target chunk list → no change."""
        sentences = [_make_sentence(1000, 5000)]
        align_target_subtitles(sentences, [])
        assert sentences[0].translation == ""

    def test_only_overlapping_sentence_gets_translation(self):
        """Multiple sentences — only overlapping ones get translations."""
        sentences = [
            _make_sentence(0, 2000, "erste"),
            _make_sentence(2000, 4000, "zweite"),
            _make_sentence(6000, 8000, "dritte"),
        ]
        chunks = [
            _make_chunk("first", 1500, 1000),  # overlaps sentences 0 and 1
        ]
        align_target_subtitles(sentences, chunks)
        assert sentences[0].translation == "first"
        assert sentences[1].translation == "first"
        assert sentences[2].translation == ""  # no overlap
