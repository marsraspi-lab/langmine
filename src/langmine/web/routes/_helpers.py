"""Shared helpers and constants for route blueprints."""

"""Shared helpers and constants for route blueprints."""

import json

from flask import (
    current_app,
)

from langmine.domain.models import Sentence
from langmine.domain.ports import (
    AudioProcessor,
    ImageSearch,
    LanguageProcessor,
    Persistence,
    TranscriptSource,
)

VALID_SENTENCE_STATUSES = {"kept", "deleted"}
EDITABLE_FIELDS = {"reading", "translation_de", "text_segmented"}


def _get_language_code() -> str:
    """Get the current source language from config."""
    return current_app.config["LANGMINE_CONFIG"].source_language


def _get_classifier():
    """Create a SentenceClassifier from injected ports."""
    from langmine.domain.classifier import SentenceClassifier

    return SentenceClassifier(_get_processor(), _get_persistence())


def _get_persistence() -> Persistence:
    """Get the persistence port from app config."""
    return current_app.config["LANGMINE_PERSISTENCE"]


def _get_processor() -> LanguageProcessor | None:
    """Get the language processor port from app config."""
    return current_app.config.get("LANGMINE_LANGUAGE_PROCESSOR")


def _get_transcript_source() -> TranscriptSource | None:
    """Get the transcript source port from app config."""
    return current_app.config.get("LANGMINE_TRANSCRIPT_SOURCE")


def _get_sentence_or_404(persistence: Persistence, sentence_id: int) -> Sentence:
    """Get a sentence by ID, raise 404 if not found."""
    from flask import abort

    # Persistence doesn't have get_sentence_by_id — search all videos
    videos = persistence.list_videos()
    for video in videos:
        sentences = persistence.get_sentences_by_video(video.id)
        for s in sentences:
            if s.id == sentence_id:
                return s
    abort(404, description=f"Sentence {sentence_id} not found")


def _get_audio_processor() -> AudioProcessor | None:
    """Get the audio processor port from app config."""
    return current_app.config.get("LANGMINE_AUDIO_PROCESSOR")


def _get_image_searcher() -> ImageSearch | None:
    """Get the image search port from app config."""
    return current_app.config.get("LANGMINE_IMAGE_SEARCHER")


def _reclassify_from_segmented(
    persistence: Persistence,
    sentence: Sentence,
) -> None:
    """Re-classify a sentence based on its manually-edited text_segmented.

    Parses the "word / word / word" format, filters non-words, and
    counts unknown words against the known vocabulary. Updates
    sentence.status, sentence.unknown_word, and sentence.unknown_word_rank.
    """
    processor = _get_processor()
    if processor is None:
        return

    known_words = persistence.get_known_words()

    # Parse tokens from "word1 / word2 / word3"
    tokens = [t.strip() for t in sentence.text_segmented.split(" / ") if t.strip()]

    # Filter non-words
    content_words = [t for t in tokens if not processor.is_non_word(t)]

    # Count unknowns
    unknown_words = [w for w in content_words if w not in known_words]
    unknown_count = len(unknown_words)

    if unknown_count == 0:
        sentence.status = "i0"
        sentence.unknown_word = None
        sentence.unknown_word_rank = None
    elif unknown_count == 1:
        word = unknown_words[0]
        sentence.status = "i1"
        sentence.unknown_word = word
        sentence.unknown_word_rank = processor.get_frequency(word)
    else:
        sentence.status = "stashed"
        sentence.unknown_word = None
        sentence.unknown_word_rank = None


def _find_sentence(persistence: Persistence, sentence_id: int) -> Sentence | None:
    """Find a sentence by id across all videos. Brute-force for simplicity."""
    for video in persistence.list_videos():
        sentences = persistence.get_sentences_by_video(video.id)
        for s in sentences:
            if s.id == sentence_id:
                return s
    return None


def _video_with_counts(persistence: Persistence, video, lang: str = "") -> dict:
    """Build a video dict with sentence counts by status."""
    sentences = persistence.get_sentences_by_video(video.id, language_code=lang)
    counts = {
        "total": 0,
        "i1": 0,
        "i0": 0,
        "stashed": 0,
        "kept": 0,
        "deleted": 0,
    }
    for s in sentences:
        counts["total"] += 1
        if s.status in counts:
            counts[s.status] += 1

    return {
        "id": video.id,
        "youtube_id": video.youtube_id,
        "title": video.title,
        "channel": video.channel,
        "duration_sec": video.duration_sec,
        "total_sentences": counts["total"],
        "i1_count": counts["i1"],
        "i0_count": counts["i0"],
        "stashed_count": counts["stashed"],
        "kept_count": counts["kept"],
        "deleted_count": counts["deleted"],
        "subtitle_language": getattr(video, "subtitle_language", ""),
        "subtitle_kind": getattr(video, "subtitle_kind", ""),
    }


def _sentence_to_dict(
    sentence: Sentence,
    persistence: Persistence | None = None,
    processor: LanguageProcessor | None = None,
) -> dict:
    """Convert a Sentence domain model to a JSON-safe dict.

    When persistence is provided, enriches with per-word status metadata
    (known/learning/unknown, frequency_rank, hsk_level).
    """
    from langmine.domain.models import frequency_badge

    result = {
        "id": sentence.id,
        "video_id": sentence.video_id,
        "text": sentence.text,
        "text_segmented": sentence.text_segmented,
        "reading": sentence.reading,
        "translation_de": sentence.translation_de,
        "unknown_word": sentence.unknown_word,
        "unknown_word_rank": sentence.unknown_word_rank,
        "start_ms": sentence.start_ms,
        "end_ms": sentence.end_ms,
        "status": sentence.status,
        "has_audio": bool(sentence.audio_clip_path),
        "has_screenshot": bool(sentence.screenshot_path),
        "created_at": sentence.created_at,
        "updated_at": sentence.updated_at,
    }

    # Compute frequency badge from rank
    result["frequency_badge"] = frequency_badge(sentence.unknown_word_rank)

    # Annotations — parse JSON, fallback to empty list
    try:
        result["annotation"] = (
            json.loads(sentence.annotation_json) if sentence.annotation_json else []
        )
    except (json.JSONDecodeError, TypeError):
        result["annotation"] = []

    # Enrich with per-word metadata for highlighting
    if persistence is not None:
        result["words"] = _words_array(sentence, persistence, processor)

    return result


def _words_array(
    sentence: Sentence,
    persistence: Persistence,
    processor: LanguageProcessor | None = None,
) -> list[dict]:
    """Build the words[] array for a sentence with status/metadata per token."""
    from langmine.language_factory import get_proficiency_level as get_hsk_level

    tokens = [t.strip() for t in sentence.text_segmented.split(" / ") if t.strip()]
    if not tokens:
        return []

    known_words = persistence.get_known_words()
    result = []
    for token in tokens:
        vocab = persistence.get_vocab_word(token)
        status = "unknown"
        frequency_rank = None
        hsk_level = get_hsk_level(token, _get_language_code())

        if vocab:
            status = vocab.status
            frequency_rank = vocab.frequency_rank
        elif token in known_words:
            status = "known"

        # Proper name detection — skip if user has any explicit vocab status
        if (
            status not in ("known", "ignored", "proper-name", "learning")
            and processor
            and processor.is_proper_name(token, context_sentence=sentence.text)
        ):
            status = "proper-name"

        result.append(
            {
                "token": token,
                "status": status,
                "frequency_rank": frequency_rank,
                "hsk_level": hsk_level,
            }
        )
    return result


def _vocab_to_dict(word, persistence: Persistence | None = None) -> dict:
    """Convert a VocabWord to a JSON-safe dict with sentence count."""
    from langmine.domain.models import frequency_badge
    from langmine.language_factory import get_proficiency_level as get_hsk_level

    sentence_count = 0
    if persistence and word.word_simplified:
        sentences = persistence.get_sentences_by_word(word.word_simplified)
        sentence_count = len(sentences)

    hsk = word.hsk_level or get_hsk_level(word.word_simplified, _get_language_code())
    rank = word.frequency_rank

    return {
        "word": word.word_simplified,
        "reading": word.reading,
        "definition_de": word.definition_de,
        "definition_en": "",  # VocabWord doesn't store EN; filled if needed
        "hsk_level": hsk,
        "frequency_rank": rank,
        "frequency_badge": frequency_badge(rank),
        "status": word.status,
        "sentence_count": sentence_count,
        "created_at": word.created_at,
        "updated_at": word.updated_at,
    }


def _unknown_word_dict(word: str, persistence: Persistence) -> dict:
    """Build a vocab dict for a word not yet in the vocab table."""
    from langmine.language_factory import get_proficiency_level as get_hsk_level

    sentences = persistence.get_sentences_by_word(word)
    hsk = get_hsk_level(word, _get_language_code())

    return {
        "word": word,
        "reading": "",
        "definition_de": "",
        "definition_en": "",
        "hsk_level": hsk,
        "frequency_rank": None,
        "frequency_badge": "",
        "status": "unknown",
        "sentence_count": len(sentences),
    }
