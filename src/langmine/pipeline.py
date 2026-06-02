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





def mine_one_sentence(
    transcript_source: TranscriptSource,
    audio_processor: AudioProcessor,
    video_id: str,
    output_dir: str,
    gap_ms: int | None = None,
    pad_before_ms: int | None = None,
    pad_after_ms: int | None = None,
    progress_callback=None,
) -> dict:
    """Extract the first sentence from a video using injected ports.

    Args:
        transcript_source: Where to get subtitles from (YouTube, Netflix, etc.)
        audio_processor: Where to download/clip audio (yt-dlp, local, etc.)
        video_id: YouTube video ID or URL.
        output_dir: Directory for audio downloads and clips.
        gap_ms, pad_before_ms, pad_after_ms: Override config defaults.

    Returns:
        Dict with keys: text, start_ms, end_ms, audio_path.
    """
    config = load_config()

    if gap_ms is None:
        gap_ms = config.sentence_gap_ms
    if pad_before_ms is None:
        pad_before_ms = config.audio_pad_before_ms
    if pad_after_ms is None:
        pad_after_ms = config.audio_pad_after_ms

    # 1. Fetch transcript through the TranscriptSource port
    chunks = transcript_source.fetch(video_id)
    sentences = merge_sentences(chunks, gap_ms=gap_ms)

    if not sentences:
        raise ValueError("No sentences could be extracted from the video.")

    first = sentences[0]

    # 2. Download full audio through the AudioProcessor port
    audio_path = audio_processor.download(video_id, output_dir=output_dir)

    # 3. Clip the first sentence through the AudioProcessor port
    clip_dir = f"{output_dir}/clips"
    clip_path = audio_processor.clip(
        audio_path=audio_path,
        start_ms=first.start_ms,
        end_ms=first.end_ms,
        pad_before_ms=pad_before_ms,
        pad_after_ms=pad_after_ms,
        output_dir=clip_dir,
        sentence_id="0001",
    )

    return {
        "text": first.text,
        "start_ms": first.start_ms,
        "end_ms": first.end_ms,
        "audio_path": clip_path,
    }


def extract_one_sentence(
    video_url: str,
    output_dir: str,
    gap_ms: int | None = None,
    pad_before_ms: int | None = None,
    pad_after_ms: int | None = None,
    progress_callback=None,
) -> dict:
    """Convenience wrapper: mine with default YouTube + yt-dlp adapters.

    This is the "quick start" API that wires up real adapters.
    For testing or swapping backends, use mine_one_sentence() directly.
    """
    from langmine.adapters import YouTubeTranscriptAdapter, YtdlpAudioAdapter

    return mine_one_sentence(
        transcript_source=YouTubeTranscriptAdapter(),
        audio_processor=YtdlpAudioAdapter(),
        video_id=video_url,
        output_dir=output_dir,
        gap_ms=gap_ms,
        pad_before_ms=pad_before_ms,
        pad_after_ms=pad_after_ms,
    )


def process_video(
    transcript_source: TranscriptSource,
    audio_processor: AudioProcessor,
    persistence: Persistence,
    language_processor: LanguageProcessor,
    video_id: str,
    output_dir: str,
    max_cards: int | None = None,
    gap_ms: int | None = None,
    pad_before_ms: int | None = None,
    pad_after_ms: int | None = None,
    progress_callback=None,
    subtitle_kind: str = "",
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

    if max_cards is None:
        max_cards = config.max_cards_per_video
    if gap_ms is None:
        if subtitle_kind == "auto":
            gap_ms = 700   # auto-generated subs have no punctuation cues
        elif subtitle_kind == "manual":
            gap_ms = 300   # manual subs are well-punctuated
        else:
            gap_ms = config.sentence_gap_ms

    # 1. Fetch and merge transcript
    _progress("Fetching transcript…")
    try:
        chunks = transcript_source.fetch(video_id, language=subtitle_language)
    except Exception as e:
        raise MineError(str(e), "transcript") from e
    merged = merge_sentences(chunks, gap_ms=gap_ms)

    if not merged:
        raise MineError("No sentences could be extracted from the video.", "transcript")

    # 2. Save video metadata
    video = Video(
        youtube_id=video_id,
        title=video_id,  # Title fetched later (M3/M7)
        language_code=config.source_language,
    )
    persistence.save_video(video)

    # 3. Classify sentences
    _progress("Classifying sentences…")
    try:
        classifier = SentenceClassifier(language_processor, persistence)
        sentences = classifier.classify(
            video_id=video.id,
            sentences=merged,
            max_cards=max_cards,
        )
    except Exception as e:
        raise MineError(str(e), "classification") from e

    # 3b. Stamp language_code on all sentences
    for s in sentences:
        s.language_code = config.source_language

    # 3c. Proficiency bootstrapping: pre-mark proficiency-framework words as known
    language_processor.bootstrap_proficiency(persistence, max_level=int(config.hsk_bootstrap_level), language_code=config.source_language)

    # 4. Enrich with NLP (pinyin, translation, definitions)
    _progress("Enriching with translations…")
    try:
        classifier.enrich(sentences)
    except Exception as e:
        raise MineError(str(e), "enrichment") from e

    # 4b. Capture screenshots for non-trivial sentences
    screenshot_dir = f"{output_dir}/screenshots"
    total_screenshots = sum(1 for s in sentences if s.screenshot_enabled and s.status != "i0")
    captured = 0
    for i, s in enumerate(sentences):
        if s.screenshot_enabled and s.status != "i0":
            try:
                s.screenshot_path = audio_processor.capture_frame(
                    video_id=video_id,
                    timestamp_ms=s.start_ms,
                    output_dir=screenshot_dir,
                    sentence_id=str(i + 1).zfill(4),
                ) or ""
                if s.screenshot_path:
                    captured += 1
                    _progress(f"Screenshot saved: {s.screenshot_path}")
                else:
                    _progress(f"Screenshot skipped for sentence {i + 1}")
            except Exception as e:
                _progress(f"Screenshot failed for sentence {i + 1}: {e}")
                s.screenshot_path = ""

    if total_screenshots > 0:
        _progress(f"Screenshots: {captured}/{total_screenshots} captured")

    # 5. Persist classified sentences
    persistence.save_sentences(sentences)

    # 5b. Log classification events for timeline
    for s in sentences:
        action = f"classified_{s.status}"
        persistence.log_event(
            entity_type="sentence", entity_id=s.id or 0,
            action=action, new_value=s.status,
            language_code=s.language_code,
        )

    # 5. Build summary
    i1_candidates = [s for s in sentences if s.status == "i1"]
    i0_count = sum(1 for s in sentences if s.status == "i0")
    stash_count = sum(1 for s in sentences if s.status == "stashed")

    return {
        "i1_candidates": i1_candidates,
        "i0_count": i0_count,
        "stash_count": stash_count,
        "total_sentences": len(sentences),
        "video_id": video_id,
    }
