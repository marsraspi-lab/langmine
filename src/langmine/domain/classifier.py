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

    def enrich(
        self,
        sentences: list[Sentence],
    ) -> list[Sentence]:
        """Populate NLP fields: pinyin, translation, word definitions, frequency badges.

        Mutates sentences in place and returns them.
        Only enriches i+1 and kept sentences (the ones shown to the user).
        """
        for sentence in sentences:
            # Reading for all sentences
            sentence.reading = self._processor.get_reading(sentence.text)

            # Annotations for all sentences
            sentence.annotation_json = self._processor.get_annotation(sentence.text)

            # Translation and word info for i+1 and kept sentences
            if sentence.status in ("i1", "kept"):
                sentence.translation_de = self._processor.translate_sentence(sentence.text)

                if sentence.unknown_word:
                    entry = self._processor.lookup_word(sentence.unknown_word)
                    if entry:
                        sentence.known_synonyms_json = str(
                            self._processor.find_known_synonyms(
                                sentence.unknown_word,
                                self._persistence.get_known_words(),
                            )
                        )

        return sentences

    def reclassify_stashed(self, video_id: int) -> int:
        """Re-classify stashed sentences for a video after vocab changes.

        When a word is marked learned or ignored, stashed sentences may
        drop to exactly 1 unknown word — promoting them to i+1.

        Returns count of sentences promoted to i+1.
        """
        known_words = self._persistence.get_known_words()
        stashed = self._persistence.get_sentences_by_video(
            video_id, status="stashed"
        )
        promoted = 0
        for s in stashed:
            tokens = [t.strip() for t in s.text_segmented.split(" / ") if t.strip()]
            if not tokens:
                continue
            content_words = [
                t for t in tokens if not self._processor.is_non_word(t)
            ]
            unknown = [w for w in content_words if w not in known_words]
            unknown_count = len(unknown)
            old_status = s.status
            if unknown_count == 0:
                s.status = "i0"
                self._persistence.update_sentence(s)
            elif unknown_count == 1:
                s.status = "i1"
                s.unknown_word = unknown[0]
                s.unknown_word_rank = self._processor.get_frequency(unknown[0])
                self._persistence.update_sentence(s)
                promoted += 1
            # unknown_count >= 2: stays stashed — no change
        return promoted
