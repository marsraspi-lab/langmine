"""Sentence classifier — the i+1 engine.

Pure domain logic. Depends only on LanguageProcessor, SentenceRepository,
and VocabRepository ports. Testable with fake ports — no YouTube, ffmpeg,
or SQLite required.
"""

from langmine.domain.models import Sentence
from langmine.domain.ports import (
    LanguageProcessor,
    MergedSentence,
    Persistence,
    SentenceRepository,
    VocabRepository,
)


class SentenceClassifier:
    """Classifies sentences into i+1, i+0, or stashed based on known vocabulary.

    Injected with ports:
      - LanguageProcessor: for segmentation, frequency, non-word detection
      - SentenceRepository: for sentence queries and updates
      - VocabRepository: for known vocabulary lookup

    Accepts Persistence for backwards compatibility (it implements both
    SentenceRepository and VocabRepository). Internally stores the narrow
    interfaces — the classifier only needs 3 of 17 Persistence methods.
    """

    def __init__(
        self,
        language_processor: LanguageProcessor,
        persistence: Persistence,
    ):
        self._processor = language_processor
        self._sentence_repo: SentenceRepository = persistence
        self._vocab_repo: VocabRepository = persistence

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
        known_words = self._vocab_repo.get_known_words()

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
        Translates all sentences regardless of status.
        Word-level synonyms are only populated for i+1 and kept sentences.
        """
        for sentence in sentences:
            # Reading for all sentences
            sentence.reading = self._processor.get_reading(sentence.text)

            # Annotations for all sentences
            sentence.annotation_json = self._processor.get_annotation(sentence.text)

            # Translation: use subtitle-aligned text if available,
            # otherwise fall back to MT (Google Translate).
            if not sentence.translation:
                sentence.translation = self._processor.translate_sentence(sentence.text)

            # Word-level synonyms for i+1 and kept sentences only
            if sentence.status in ("i1", "kept") and sentence.unknown_word:
                entry = self._processor.lookup_word(sentence.unknown_word)
                if entry:
                    sentence.known_synonyms_json = str(
                        self._processor.find_known_synonyms(
                            sentence.unknown_word,
                            self._vocab_repo.get_known_words(),
                        )
                    )

        return sentences

    def reclassify_all(self, video_id: int) -> list[Sentence]:
        """Re-classify ALL sentences for a video after vocab changes (M22).

        Re-counts unknown words per sentence using current known_words.
        Updates status and unknown_word fields in place.
        Returns sentences sorted by best-candidate-first:
        i1 (by frequency, most common first), then i0, then stashed.
        """
        known_words = self._vocab_repo.get_known_words()
        sentences = self._sentence_repo.get_sentences_by_video(video_id)

        i1_candidates: list[Sentence] = []
        i0_sentences: list[Sentence] = []
        stashed: list[Sentence] = []

        for s in sentences:
            tokens = [t.strip() for t in s.text_segmented.split(" / ") if t.strip()]
            if not tokens:
                i0_sentences.append(s)
                continue

            content_words = [t for t in tokens if not self._processor.is_non_word(t)]
            unknown = [w for w in content_words if w not in known_words]
            unknown_count = len(unknown)

            if unknown_count == 0:
                s.status = "i0"
                s.unknown_word = ""
                s.unknown_word_rank = None
                i0_sentences.append(s)
            elif unknown_count == 1:
                s.status = "i1"
                s.unknown_word = unknown[0]
                s.unknown_word_rank = self._processor.get_frequency(unknown[0])
                i1_candidates.append(s)
            else:
                s.status = "stashed"
                s.unknown_word = ""
                s.unknown_word_rank = None
                stashed.append(s)

            self._sentence_repo.update_sentence(s)

        # Sort i1 by frequency (most common first, None sorts last)
        i1_candidates.sort(
            key=lambda s: (
                s.unknown_word_rank is None,
                s.unknown_word_rank or 0,
            )
        )

        results = i1_candidates + i0_sentences + stashed

        # Re-enrich after reclassification so sentences get fresh translations,
        # readings, and annotations (B3).
        self.enrich(results)
        for s in results:
            self._sentence_repo.update_sentence(s)

        return results
