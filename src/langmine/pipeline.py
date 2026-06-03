"""End-to-end sentence mining pipeline using domain ports.

The pipeline depends on ports (interfaces), not on concrete adapters.
This means you can swap YouTube for Netflix, yt-dlp for local audio files,
or SQLite for JSON files without changing this code.
"""

from langmine.domain.ports import (
    TranscriptSource,
    AudioProcessor,
    Persistence,
    LanguageProcessor,
)
from langmine.domain.models import Video, Sentence
from langmine.domain.classifier import SentenceClassifier
from langmine.transcript import merge_sentences
from langmine.config import load_config


class MineError(Exception):
    """Pipeline error with a stage identifier for frontend display."""

    def __init__(self, message: str, stage: str):
        super().__init__(message)
        self.stage = stage


def process_video(
    transcript_source: TranscriptSource,
    audio_processor: AudioProcessor,
    persistence: Persistence,
    language_processor: LanguageProcessor,
    video_id: str,
    output_dir: str,
    progress_callback=None,
    subtitle_language: str = "",
) -> dict:
    """Mine and classify all sentences from a video.

    Full pipeline: transcript → merge → classify → persist.
    Uses injected ports — no direct YouTube/ffmpeg/SQLite dependencies.

    Returns:
        Dict with: i1_candidates (list[Sentence]), i0_count, stash_count,
        total_sentences, video_id.
    """
    def _progress(msg):
        if progress_callback:
            progress_callback(msg)

    config = load_config()
    max_cards = config.max_cards_per_video
    gap_ms = config.sentence_gap_ms

    # 1. Fetch and merge transcript
    _progress("Fetching transcript…")
    merged = _fetch_and_merge_transcript(transcript_source, video_id, subtitle_language, gap_ms)

    # 2. Save video metadata
    video = Video(
        youtube_id=video_id,
        title=video_id,  # Title fetched later (M3/M7)
        language_code=config.source_language,
    )
    persistence.save_video(video)

    # 3. Classify and bootstrap
    _progress("Classifying sentences…")
    classifier = SentenceClassifier(language_processor, persistence)
    sentences = _classify_and_bootstrap(
        classifier, language_processor, persistence, video, merged, max_cards, config
    )

    # 4. Enrich and capture screenshots
    _progress("Enriching with translations…")
    _enrich_and_capture_screenshots(
        classifier, audio_processor, sentences, video_id, output_dir, _progress
    )

    # 5. Persist and log
    _persist_and_log(persistence, sentences)

    # 6. Build summary
    return _build_summary(sentences, video_id)


def _fetch_and_merge_transcript(
    transcript_source: TranscriptSource,
    video_id: str,
    subtitle_language: str,
    gap_ms: int,
) -> list:
    try:
        chunks = transcript_source.fetch(video_id, language=subtitle_language)
    except Exception as e:
        raise MineError(str(e), "transcript") from e

    merged = merge_sentences(chunks, gap_ms=gap_ms)
    if not merged:
        raise MineError("No sentences could be extracted from the video.", "transcript")
    return merged


def _classify_and_bootstrap(
    classifier: SentenceClassifier,
    language_processor: LanguageProcessor,
    persistence: Persistence,
    video: Video,
    merged: list,
    max_cards: int,
    config,
) -> list[Sentence]:
    try:
        sentences = classifier.classify(
            video_id=video.id,
            sentences=merged,
            max_cards=max_cards,
        )
    except Exception as e:
        raise MineError(str(e), "classification") from e

    for s in sentences:
        s.language_code = config.source_language

    language_processor.bootstrap_proficiency(
        persistence,
        max_level=int(config.hsk_bootstrap_level),
        language_code=config.source_language
    )
    return sentences


def _enrich_and_capture_screenshots(
    classifier: SentenceClassifier,
    audio_processor: AudioProcessor,
    sentences: list[Sentence],
    video_id: str,
    output_dir: str,
    progress_fn,
) -> None:
    try:
        classifier.enrich(sentences)
    except Exception as e:
        raise MineError(str(e), "enrichment") from e

    screenshot_dir = f"{output_dir}/screenshots"
    total_screenshots = sum(1 for s in sentences if s.screenshot_enabled and s.status != "i0")
    captured = 0

    for i, s in enumerate(sentences):
        if not s.screenshot_enabled or s.status == "i0":
            continue

        try:
            s.screenshot_path = audio_processor.capture_frame(
                video_id=video_id,
                timestamp_ms=s.start_ms,
                output_dir=screenshot_dir,
                sentence_id=str(i + 1).zfill(4),
            ) or ""
            if s.screenshot_path:
                captured += 1
                progress_fn(f"Screenshot saved: {s.screenshot_path}")
            else:
                progress_fn(f"Screenshot skipped for sentence {i + 1}")
        except Exception as e:
            progress_fn(f"Screenshot failed for sentence {i + 1}: {e}")
            s.screenshot_path = ""

    if total_screenshots > 0:
        progress_fn(f"Screenshots: {captured}/{total_screenshots} captured")


def _persist_and_log(persistence: Persistence, sentences: list[Sentence]) -> None:
    persistence.save_sentences(sentences)
    for s in sentences:
        persistence.log_event(
            entity_type="sentence",
            entity_id=s.id or 0,
            action=f"classified_{s.status}",
            new_value=s.status,
            language_code=s.language_code,
        )


def _build_summary(sentences: list[Sentence], video_id: str) -> dict:
    return {
        "i1_candidates": [s for s in sentences if s.status == "i1"],
        "i0_count": sum(1 for s in sentences if s.status == "i0"),
        "stash_count": sum(1 for s in sentences if s.status == "stashed"),
        "total_sentences": len(sentences),
        "video_id": video_id,
    }

