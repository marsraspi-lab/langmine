"""Align target-language subtitles to source sentences by time overlap.

Pure function — no I/O, no side effects beyond mutating the Sentence
objects in place.
"""

from langmine.domain.models import Sentence
from langmine.domain.ports import TranscriptChunk


def align_target_subtitles(
    sentences: list[Sentence],
    target_chunks: list[TranscriptChunk],
) -> None:
    """Set sentence.translation from overlapping target subtitle chunks.

    For each sentence, finds all target subtitle chunks whose time window
    overlaps with the sentence's [start_ms, end_ms] window, concatenates
    their text, and sets sentence.translation.

    Sentences with no overlapping target chunks are left as-is (their
    translation remains empty, to be filled by MT during enrichment).
    """
    for sentence in sentences:
        matches = [
            c.text
            for c in target_chunks
            if c.start_ms < sentence.end_ms
            and (c.start_ms + c.duration_ms) > sentence.start_ms
        ]
        if matches:
            sentence.translation = " ".join(matches)
