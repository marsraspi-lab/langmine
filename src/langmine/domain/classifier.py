"""Sentence classifier — the i+1 engine.

Pure domain logic. Depends only on LanguageProcessor and Persistence ports.
Testable with fake ports — no YouTube, ffmpeg, or SQLite required.
"""

from langmine.domain.ports import (
    LanguageProcessor,
    Persistence,
    MergedSentence,
)
from langmine.domain.models import Sentence


class SentenceClassifier:
    """Classifies sentences into i+1, i+0, or stashed based on known vocabulary.

    Injected with ports:
      - LanguageProcessor: for segmentation, frequency, non-word detection
      - Persistence: for known vocabulary lookup
    """

    def __init__(
        self,
        language_processor: LanguageProcessor,
        persistence: Persistence,
    ):
        self._processor = language_processor
        self._persistence = persistence

    def classify(
        self,
        video_id: int,
        sentences: list[MergedSentence],
        max_cards: int = 20,
    ) -> list[Sentence]:
        """Classify all sentences from a video.

        Args:
            video_id: The video these sentences belong to.
            sentences: Merged sentences from the transcript.
            max_cards: Maximum i+1 candidates to return (cap).

        Returns:
            All sentences with status set to i1, i0, or stashed.
            i+1 sentences sorted by frequency rank (most common first).
            i+1 sentences capped at max_cards.
            i+0 and stashed sentences not capped.
        """
        known_words = self._persistence.get_known_words()

        results: list[Sentence] = []
        i1_candidates: list[Sentence] = []

        for merged in sentences:
            # Segment into words
            tokens = self._processor.segment(merged.text)

            # Filter out non-words (particles, numbers, names, dates)
            content_words = [t for t in tokens if not self._processor.is_non_word(t)]

            # Count unknown words
            unknown_words = [w for w in content_words if w not in known_words]
            unknown_count = len(unknown_words)

            # Build sentence object
            sentence = Sentence(
                video_id=video_id,
                start_ms=merged.start_ms,
                end_ms=merged.end_ms,
                text=merged.text,
                text_segmented=" / ".join(tokens),
            )

            if unknown_count == 0:
                sentence.status = "i0"
                results.append(sentence)

            elif unknown_count == 1:
                word = unknown_words[0]
                sentence.status = "i1"
                sentence.unknown_word = word
                sentence.unknown_word_rank = self._processor.get_frequency(word)
                i1_candidates.append(sentence)

            else:  # unknown_count >= 2
                sentence.status = "stashed"
                results.append(sentence)

        # Sort i+1 candidates by frequency rank (ascending = most common first)
        # Words with no frequency data (None) sort to the end
        i1_candidates.sort(
            key=lambda s: (
                s.unknown_word_rank is None,  # None sorts after numbers
                s.unknown_word_rank or 0,
            )
        )

        # Cap i+1 candidates
        capped_i1 = i1_candidates[:max_cards]

        return capped_i1 + results
