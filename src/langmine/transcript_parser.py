"""Parse SRT and VTT subtitle files into TranscriptChunk lists.

Used as a fallback when youtube-transcript-api is IP-blocked.
Users can download subtitles from their browser and upload them.
"""

import re
from langmine.domain.ports import TranscriptChunk


def parse_subtitle_file(content: str, filename: str = "") -> list[TranscriptChunk]:
    """Parse an SRT or VTT subtitle file into TranscriptChunk objects.

    Detects format by extension (.srt, .vtt) or by content heuristics.

    Args:
        content: Raw text content of the subtitle file.
        filename: Optional filename for format detection by extension.

    Returns:
        List of TranscriptChunk objects with text and millisecond timing.

    Raises:
        ValueError: If the format is unrecognized or parsing fails.
    """
    if filename.lower().endswith(".vtt"):
        return _parse_vtt(content)
    if filename.lower().endswith(".srt"):
        return _parse_srt(content)
    # Heuristic: VTT starts with "WEBVTT"
    if content.lstrip().startswith("WEBVTT"):
        return _parse_vtt(content)
    # Default to SRT
    return _parse_srt(content)


def _parse_srt(content: str) -> list[TranscriptChunk]:
    """Parse SRT format: index, timestamp range, text, blank line."""
    chunks: list[TranscriptChunk] = []

    # SRT blocks are separated by blank lines
    blocks = re.split(r"\n\s*\n", content.strip())
    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 2:
            continue

        # Find the timestamp line (contains "-->")
        ts_line = ""
        text_lines = []
        for line in lines:
            if "-->" in line:
                ts_line = line
            elif ts_line:
                text_lines.append(line.strip())

        if not ts_line or not text_lines:
            continue

        start_ms, end_ms = _parse_srt_timestamp(ts_line)
        duration_ms = max(0, end_ms - start_ms)
        text = " ".join(text_lines)

        # Remove HTML tags (common in YouTube VTT exports saved as SRT)
        text = re.sub(r"<[^>]+>", "", text)
        text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")

        if text.strip():
            chunks.append(TranscriptChunk(
                text=text.strip(),
                start_ms=start_ms,
                duration_ms=duration_ms,
            ))

    return chunks


def _parse_vtt(content: str) -> list[TranscriptChunk]:
    """Parse WebVTT format."""
    chunks: list[TranscriptChunk] = []

    # Strip WEBVTT header and optional metadata
    lines = content.strip().split("\n")
    # Skip header line(s) until we find a timestamp
    i = 0
    while i < len(lines) and ("-->" not in lines[i]):
        i += 1

    while i < len(lines):
        line = lines[i].strip()
        if "-->" in line:
            start_ms, end_ms = _parse_vtt_timestamp(line)
            text_parts = []
            i += 1
            while i < len(lines) and lines[i].strip() and "-->" not in lines[i]:
                text_parts.append(lines[i].strip())
                i += 1
            text = " ".join(text_parts)
            if text.strip():
                text = re.sub(r"<[^>]+>", "", text)
                text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
                chunks.append(TranscriptChunk(
                    text=text.strip(),
                    start_ms=start_ms,
                    duration_ms=max(0, end_ms - start_ms),
                ))
        else:
            i += 1

    return chunks


def _parse_srt_timestamp(line: str) -> tuple[int, int]:
    """Parse '00:01:23,456 --> 00:01:27,890' into (start_ms, end_ms)."""
    match = re.match(
        r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{1,2}):(\d{2}):(\d{2})[,.](\d{3})",
        line,
    )
    if not match:
        raise ValueError(f"Invalid SRT timestamp: {line}")
    h1, m1, s1, ms1, h2, m2, s2, ms2 = map(int, match.groups())
    start = ((h1 * 60 + m1) * 60 + s1) * 1000 + ms1
    end = ((h2 * 60 + m2) * 60 + s2) * 1000 + ms2
    return start, end


def _parse_vtt_timestamp(line: str) -> tuple[int, int]:
    """Parse '00:01:23.456 --> 00:01:27.890' into (start_ms, end_ms)."""
    # VTT uses periods instead of commas for milliseconds
    match = re.match(
        r"(\d{1,2}):(\d{2}):(\d{2})[.,](\d{3})\s*-->\s*(\d{1,2}):(\d{2}):(\d{2})[.,](\d{3})",
        line,
    )
    if not match:
        raise ValueError(f"Invalid VTT timestamp: {line}")
    h1, m1, s1, ms1, h2, m2, s2, ms2 = map(int, match.groups())
    start = ((h1 * 60 + m1) * 60 + s1) * 1000 + ms1
    end = ((h2 * 60 + m2) * 60 + s2) * 1000 + ms2
    return start, end
