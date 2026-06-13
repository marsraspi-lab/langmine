"""Transcript utilities — YouTube subtitle download, SRT parsing, sentence merging.

Concrete functions (not a port/adapter): fetches subtitles via yt-dlp --write-sub,
parses SRT format into TranscriptChunks, merges adjacent chunks into sentences
based on a pause threshold, and lists available subtitle tracks.
Used by YouTubeTranscriptAdapter and the inline-transcript upload path.
"""

import re
import subprocess
import tempfile
from pathlib import Path

from langmine.domain.ports import MergedSentence, SubtitleInfo, TranscriptChunk


def fetch_transcript(
    video_id_or_url: str, user_agent: str = "", language_codes: list[str] | None = None
) -> list[TranscriptChunk]:
    """Fetch subtitle chunks for a YouTube video via yt-dlp.

    Downloads subtitles as SRT, then parses them into TranscriptChunk objects.

    Args:
        video_id_or_url: YouTube video ID (11 chars) or full URL.
        user_agent: Optional custom User-Agent for yt-dlp.
        language_codes: Optional list of language codes to prefer (e.g.,
            ['zh-Hans', 'zh']). First matching code is used as --sub-lang.

    Returns:
        List of transcript chunks with text and timing.

    Raises:
        ValueError: If the video ID is invalid or transcript unavailable.
    """
    video_id = _extract_video_id(video_id_or_url)
    url = f"https://www.youtube.com/watch?v={video_id}"

    # Determine subtitle language
    sub_lang = _pick_sub_lang(language_codes)

    with tempfile.TemporaryDirectory() as tmpdir:
        out_tmpl = str(Path(tmpdir) / "%(id)s.%(ext)s")
        cmd = [
            "yt-dlp",
            "--write-sub",
            "--sub-lang",
            sub_lang,
            "--sub-format",
            "srt",
            "--skip-download",
            "--no-playlist",
            "--no-warnings",
            "-o",
            out_tmpl,
        ]
        if user_agent:
            cmd.insert(1, "--user-agent")
            cmd.insert(2, user_agent)
        cmd.append(url)

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        stderr = result.stderr.lower() if result.stderr else ""

        if result.returncode != 0:
            if "video unavailable" in stderr or "private video" in stderr:
                raise ValueError(f"Video '{video_id}' is unavailable or private.")
            elif "429" in stderr or "blocked" in stderr:
                raise ValueError(
                    "YouTube is blocking requests from this IP address. "
                    "Options:\n"
                    "  • Wait a few hours — blocks are usually temporary\n"
                    "  • Use a VPN or different network\n"
                    "  • Set a custom User-Agent in Settings (network.user_agent)\n"
                    "  • Use a transcript file (.srt/.vtt) via the upload option"
                )
            else:
                raise ValueError(
                    f"No transcript available for video '{video_id}'. "
                    f"The video may not have subtitles or they may be disabled."
                )

        # Find the downloaded SRT file
        srt_files = list(Path(tmpdir).glob(f"{video_id}*.srt"))
        if not srt_files:
            # yt-dlp might name the file differently if --sub-lang produced
            # a suffix like video_id.en.srt — try a broader glob
            srt_files = list(Path(tmpdir).glob("*.srt"))

        if not srt_files:
            raise ValueError(
                f"No transcript available for video '{video_id}'. "
                f"The video may not have subtitles or they may be disabled."
            )

        return _parse_srt(srt_files[0])


def _pick_sub_lang(language_codes: list[str] | None) -> str:
    """Map language codes to yt-dlp --sub-lang field.

    Falls back to 'en' if no codes provided or none are mappable.
    """
    if not language_codes:
        return "en"

    # yt-dlp uses ISO 639-1 or ISO 639-2 codes, sometimes with region suffix.
    # Common mappings from what youtube-transcript-api uses:
    lang_map = {
        "zh-Hans": "zh-Hans",
        "zh-Hant": "zh-Hant",
        "zh-CN": "zh-Hans",
        "zh-TW": "zh-Hant",
        "zh": "zh",
        "en": "en",
        "es": "es",
        "ko": "ko",
        "ru": "ru",
        "ja": "ja",
        "fr": "fr",
        "de": "de",
        "pt": "pt",
        "it": "it",
        "ar": "ar",
        "hi": "hi",
        "th": "th",
        "vi": "vi",
        "tr": "tr",
    }
    for code in language_codes:
        mapped = lang_map.get(code)
        if mapped:
            return mapped
    return language_codes[0] if language_codes else "en"


def _parse_srt(path: Path) -> list[TranscriptChunk]:
    """Parse an SRT file into TranscriptChunk objects.

    SRT format:
        1
        00:00:01,000 --> 00:00:04,000
        First subtitle text

        2
        00:00:05,000 --> 00:00:08,000
        Second subtitle text
    """
    content = path.read_text(encoding="utf-8")
    blocks = re.split(r"\n\s*\n", content.strip())
    if not blocks:
        return []

    timestamp_re = re.compile(
        r"(\d{2}):(\d{2}):(\d{2})[.,](\d{3})\s*-->\s*"
        r"(\d{2}):(\d{2}):(\d{2})[.,](\d{3})"
    )

    chunks: list[TranscriptChunk] = []
    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 2:
            continue

        ts_idx = _find_timestamp_index(lines, timestamp_re)
        if ts_idx is None:
            continue

        ts_ms = _parse_srt_timestamp(lines[ts_idx], timestamp_re)
        if ts_ms is None:
            continue

        text = _extract_srt_text(lines, ts_idx)
        if not text:
            continue

        start_ms, duration_ms = ts_ms
        chunks.append(TranscriptChunk(
            text=text,
            start_ms=float(start_ms),
            duration_ms=float(duration_ms),
        ))

    return chunks


def _find_timestamp_index(lines: list[str], pattern: re.Pattern) -> int | None:
    """Return the index of the first line matching the timestamp pattern."""
    for i, line in enumerate(lines):
        if pattern.search(line):
            return i
    return None


def _parse_srt_timestamp(line: str, pattern: re.Pattern) -> tuple[int, int] | None:
    """Parse SRT timestamp line into (start_ms, duration_ms)."""
    match = pattern.search(line)
    if not match:
        return None
    h1, m1, s1, ms1, h2, m2, s2, ms2 = map(int, match.groups())
    start_ms = (h1 * 3600 + m1 * 60 + s1) * 1000 + ms1
    end_ms = (h2 * 3600 + m2 * 60 + s2) * 1000 + ms2
    duration_ms = max(end_ms - start_ms, 1)
    return start_ms, duration_ms


def _extract_srt_text(lines: list[str], ts_idx: int) -> str:
    """Extract subtitle text from lines after the timestamp."""
    text_lines = lines[ts_idx + 1:]
    return " ".join(line.strip() for line in text_lines if line.strip())


def _parse_list_subs_output(output: str) -> list[SubtitleInfo]:
    """Parse yt-dlp --list-subs output into SubtitleInfo objects.

    yt-dlp --list-subs produces TWO sections:
    1. "Available subtitles" — manual (human-created), kind="manual"
    2. "Available automatic captions" — auto-generated (speech recognition)
       or auto-translated from another language, kind="auto"

    Expected format:
        [info] Available subtitles for abc123:
        Language Name                  Formats
        zh-Hans  Chinese (Simplified)  vtt, srt, ttml
        en       English               vtt, srt, ttml

        [info] Available automatic captions for abc123:
        Language Name                               Formats
        zh-Hans  Chinese (Simplified)               vtt, srt, ttml (auto-generated)
        zh-Hans-en Chinese (Simplified) from English  vtt, srt, ttml, ...
    """
    subtitles = []
    section = None

    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue

        new_section = _detect_list_subs_section(line)
        if new_section:
            section = new_section
            continue

        if _is_list_subs_header(line):
            continue

        if section is None:
            continue

        parsed = _parse_subtitle_line(line)
        if parsed is None:
            continue

        lang_code, lang_name = parsed
        subtitles.append(SubtitleInfo(
            language_code=lang_code,
            language_name=lang_name,
            kind=section,
        ))

    return subtitles


def _detect_list_subs_section(line: str) -> str | None:
    """Detect section from listing header line. Returns 'manual', 'auto', or None."""
    if "Available automatic captions" in line or "Available auto-generated" in line:
        return "auto"
    if "Available subtitles" in line:
        return "manual"
    return None


def _is_list_subs_header(line: str) -> bool:
    """Check if line is the column header row."""
    return "Language" in line and "Formats" in line


def _parse_subtitle_line(line: str) -> tuple[str, str] | None:
    """Parse a subtitle listing line into (language_code, language_name)."""
    match = re.match(r"^(\S+)\s{2,}(.+?)\s+(vtt|srt|ttml|ass)(.*)$", line)
    if not match:
        return None
    lang_code = match.group(1)
    lang_name = match.group(2).strip()
    # Clean up auto-translated names: "Chinese (Simplified) from English" → "Chinese (Simplified)"
    if " from " in lang_name:
        lang_name = lang_name.rsplit(" from ", 1)[0]
    return lang_code, lang_name


def merge_sentences(
    chunks: list[TranscriptChunk], gap_ms: int = 500
) -> list[MergedSentence]:
    """Merge subtitle chunks into sentences using a pause-based heuristic.

    Adjacent chunks are merged if the time gap between them is ≤ gap_ms.
    A gap is the difference between (chunk_A.start + chunk_A.duration)
    and chunk_B.start.

    Args:
        chunks: Chronologically ordered subtitle chunks.
        gap_ms: Maximum gap in milliseconds between chunks to merge.

    Returns:
        List of merged sentences with text and timing boundaries.
    """
    if not chunks:
        return []

    sentences: list[MergedSentence] = []
    current_text = chunks[0].text.strip()
    current_start = chunks[0].start_ms
    current_end = chunks[0].start_ms + chunks[0].duration_ms

    for i in range(1, len(chunks)):
        prev_end = current_end
        next_start = chunks[i].start_ms
        gap = next_start - prev_end

        if gap <= gap_ms:
            # Merge: append text with a space
            current_text += " " + chunks[i].text.strip()
            current_end = chunks[i].start_ms + chunks[i].duration_ms
        else:
            # Split: finish current sentence, start new one
            sentences.append(
                MergedSentence(
                    text=current_text,
                    start_ms=current_start,
                    end_ms=current_end,
                )
            )
            current_text = chunks[i].text.strip()
            current_start = chunks[i].start_ms
            current_end = chunks[i].start_ms + chunks[i].duration_ms

    # Don't forget the last sentence
    sentences.append(
        MergedSentence(
            text=current_text,
            start_ms=current_start,
            end_ms=current_end,
        )
    )

    return sentences


def _extract_video_id(url_or_id: str) -> str:
    """Extract an 11-character YouTube video ID from a URL or raw ID."""
    # Already a raw video ID (11 alphanumeric + _- chars)
    if re.match(r"^[A-Za-z0-9_-]{11}$", url_or_id):
        return url_or_id

    # Try common URL patterns
    patterns = [
        r"youtube\.com/watch\?v=([A-Za-z0-9_-]{11})",
        r"youtu\.be/([A-Za-z0-9_-]{11})",
        r"youtube\.com/embed/([A-Za-z0-9_-]{11})",
        r"youtube\.com/shorts/([A-Za-z0-9_-]{11})",
        r"m\.youtube\.com/watch\?v=([A-Za-z0-9_-]{11})",
    ]

    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)

    raise ValueError(
        f"Could not extract a YouTube video ID from '{url_or_id}'. "
        f"Provide a full URL or an 11-character video ID."
    )
