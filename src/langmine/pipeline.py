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


def mine_one_sentence(
    transcript_source: TranscriptSource,
    audio_processor: AudioProcessor,
    video_id: str,
    output_dir: str,
    gap_ms: int | None = None,
    pad_before_ms: int | None = None,
    pad_after_ms: int | None = None,
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
    progress_callback: callable | None = None,
) -> dict:
    """Mine and classify all sentences from a video.

    Full pipeline: transcript → merge → classify → persist.
    Uses injected ports — no direct YouTube/ffmpeg/SQLite dependencies.

    Args:
        progress_callback: Optional callable(str) for progress updates.
            Called at each pipeline stage with a human-readable message.

    Returns:
        Dict with: i1_candidates (list[Sentence]), i0_count, stash_count,
        total_sentences, video_id.
    """
    def _progress(msg: str) -> None:
        if progress_callback:
            progress_callback(msg)

    config = load_config()

    if max_cards is None:
        max_cards = config.max_cards_per_video
    if gap_ms is None:
        gap_ms = config.sentence_gap_ms

    # 1. Fetch and merge transcript
    _progress("Fetching transcript…")
    chunks = transcript_source.fetch(video_id)
    merged = merge_sentences(chunks, gap_ms=gap_ms)
    _progress(f"Found {len(chunks)} chunks → {len(merged)} sentences")

    if not merged:
        raise ValueError("No sentences could be extracted from the video.")

    # 2. Save video metadata
    from langmine.audio import get_video_info
    _progress("Fetching video info…")
    info = get_video_info(video_id, user_agent=config.user_agent)
    video = Video(
        youtube_id=video_id,
        title=info["title"] or video_id,
        channel=info["channel"],
        duration_sec=int(info["duration_sec"]) if info["duration_sec"].isdigit() else 0,
        language_code=config.source_language,
    )
    _progress(f"📺 {info['title'] or video_id}")
    persistence.save_video(video)

    # 3. Classify sentences
    _progress("Classifying sentences…")
    classifier = SentenceClassifier(language_processor, persistence)
    sentences = classifier.classify(
        video_id=video.id,
        sentences=merged,
        max_cards=max_cards,
    )

    # 3b. Stamp language_code on all sentences
    for s in sentences:
        s.language_code = config.source_language

    i1 = sum(1 for s in sentences if s.status == "i1")
    i0 = sum(1 for s in sentences if s.status == "i0")
    stashed = sum(1 for s in sentences if s.status == "stashed")
    _progress(f"Classified: {i1} i+1, {i0} i+0, {stashed} stashed")

    # 4. Enrich with NLP (pinyin, translation, definitions)
    _progress("Enriching with translations & readings…")
    classifier.enrich(sentences)

    # 4b. Capture screenshots for non-trivial sentences
    screenshot_dir = f"{output_dir}/screenshots"
    to_screenshot = [s for s in sentences if s.screenshot_enabled and s.status != "i0"]
    for i, s in enumerate(to_screenshot):
        _progress(f"Screenshots ({i + 1}/{len(to_screenshot)})…")
        try:
            s.screenshot_path = audio_processor.capture_frame(
                video_id=video_id,
                timestamp_ms=s.start_ms,
                output_dir=screenshot_dir,
                sentence_id=str(i + 1).zfill(4),
            ) or ""
        except Exception:
            s.screenshot_path = ""

    # 5. Persist classified sentences
    _progress("Saving to database…")
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
