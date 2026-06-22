"""End-to-end sentence mining pipeline using domain ports.

The pipeline depends on ports (interfaces), not on concrete adapters.
This means you can swap YouTube for Netflix, yt-dlp for local audio files,
or SQLite for JSON files without changing this code.
"""

import json
import os

from langmine.domain.classifier import SentenceClassifier
from langmine.domain.models import Sentence, Video
from langmine.domain.ports import (
    AudioProcessor,
    LanguageProcessor,
    Persistence,
    TranscriptSource,
)
from langmine.transcript import merge_sentences


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
    config,
    progress_callback=None,
    subtitle_language: str = "",
    target_subtitle_language: str = "",
) -> dict:
    """Mine and classify all sentences from a video.

    Full pipeline: transcript → merge → classify → enrich → persist.
    Uses injected ports — no direct YouTube/ffmpeg/SQLite dependencies.

    If target_subtitle_language is provided, fetches target-language
    subtitles and uses time-overlap alignment to set sentence.translation
    before enrichment. Enrich fills gaps via MT.

    Returns:
        Dict with: i1_candidates (list[Sentence]), i0_count, stash_count,
        total_sentences, video_id.
    """

    def _progress(msg):
        if progress_callback:
            progress_callback(msg)

    max_cards = config.max_cards_per_video
    gap_ms = config.sentence_gap_ms

    # 1. Fetch transcript — cache raw chunks before merging
    _progress("Fetching transcript…")
    try:
        raw_chunks = transcript_source.fetch(video_id, language=subtitle_language)
    except Exception as e:
        raise MineError(str(e), "transcript") from e
    merged = merge_sentences(raw_chunks, gap_ms=gap_ms)
    if not merged:
        raise MineError("No sentences could be extracted from the video.", "transcript")
    raw_json = json.dumps(
        [
            {
                "text": c.text,
                "start_ms": c.start_ms,
                "duration_ms": c.duration_ms,
            }
            for c in raw_chunks
        ]
    )

    # 2. Save video metadata
    video = Video(
        youtube_id=video_id,
        title=video_id,  # Title fetched later (M3/M7)
        language_code=config.source_language,
        transcript_json=raw_json,
    )
    persistence.save_video(video)

    # 2.5 Download full audio for clipping
    _progress("Downloading audio…")
    try:
        video.audio_path = audio_processor.download(video_id, output_dir)
        persistence.save_video(video)
    except Exception:
        _progress("Audio download skipped (not available)")

    # 3. Classify and bootstrap
    _progress("Classifying sentences…")
    classifier = SentenceClassifier(language_processor, persistence)
    sentences = _classify_and_bootstrap(
        classifier, language_processor, persistence, video, merged, max_cards, config
    )

    # 3.5 Align target-language subtitles as translations (if selected)
    if target_subtitle_language:
        try:
            target_chunks = transcript_source.fetch(
                video_id, language=target_subtitle_language
            )
            if target_chunks:
                from langmine.subtitle_aligner import align_target_subtitles

                align_target_subtitles(sentences, target_chunks)
                _progress(
                    f"Aligned {sum(1 for s in sentences if s.translation)} "
                    f"translations from {target_subtitle_language} subtitles."
                )
                # Cache target transcript for re-mining
                video.target_transcript_json = json.dumps(
                    [
                        {
                            "text": c.text,
                            "start_ms": c.start_ms,
                            "duration_ms": c.duration_ms,
                        }
                        for c in target_chunks
                    ]
                )
                video.target_subtitle_language = target_subtitle_language
                persistence.save_video(video)
        except Exception:
            _progress(
                f"Target subtitle '{target_subtitle_language}' unavailable, "
                f"falling back to MT."
            )

    # 4. Enrich, capture screenshots, and clip audio
    _progress("Enriching with translations…")
    _enrich_and_capture_screenshots(
        classifier,
        audio_processor,
        sentences,
        video_id,
        output_dir,
        video.audio_path,
        config.audio_pad_before_ms,
        config.audio_pad_after_ms,
        _progress,
    )

    # 5. Persist and log
    _persist_and_log(persistence, sentences)

    # 6. Build summary
    return _build_summary(sentences, video_id)


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
        settings=config.language_settings.get(config.source_language, {}),
        language_code=config.source_language,
    )
    return sentences


def _enrich_and_capture_screenshots(
    classifier: SentenceClassifier,
    audio_processor: AudioProcessor,
    sentences: list[Sentence],
    video_id: str,
    output_dir: str,
    audio_path: str,
    pad_before_ms: int,
    pad_after_ms: int,
    progress_fn,
) -> None:
    try:
        classifier.enrich(sentences)
    except Exception as e:
        raise MineError(str(e), "enrichment") from e

    screenshot_dir = f"{output_dir}/screenshots"
    clip_dir = f"{output_dir}/clips"
    total_screenshots = sum(
        1 for s in sentences if s.screenshot_enabled and s.status != "i0"
    )
    captured = 0

    for i, s in enumerate(sentences):
        sentence_id = str(i + 1).zfill(4)

        # Screenshot (skip i0)
        if s.screenshot_enabled and s.status != "i0":
            try:
                s.screenshot_path = (
                    audio_processor.capture_frame(
                        video_id=video_id,
                        timestamp_ms=s.start_ms,
                        output_dir=screenshot_dir,
                        sentence_id=sentence_id,
                    )
                    or ""
                )
                if s.screenshot_path:
                    captured += 1
                    progress_fn(f"Screenshot saved: {s.screenshot_path}")
                else:
                    progress_fn(f"Screenshot skipped for sentence {i + 1}")
            except Exception as e:
                progress_fn(f"Screenshot failed for sentence {i + 1}: {e}")
                s.screenshot_path = ""

        # Audio clip (all sentences, best effort)
        if audio_path:
            try:
                os.makedirs(clip_dir, exist_ok=True)
                s.audio_clip_path = audio_processor.clip(
                    audio_path=audio_path,
                    start_ms=s.start_ms,
                    end_ms=s.end_ms,
                    pad_before_ms=pad_before_ms,
                    pad_after_ms=pad_after_ms,
                    output_dir=clip_dir,
                    sentence_id=sentence_id,
                )
            except Exception:
                pass  # best effort — audio clipping may not be available

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
