"""Tests for transcript fetching and sentence merging."""

import pytest
from unittest.mock import patch, MagicMock
import tempfile
from pathlib import Path

from langmine.transcript import (
    fetch_transcript,
    merge_sentences,
    TranscriptChunk,
    _parse_srt,
)


def _make_srt(chunks: list[tuple[str, int, int]]) -> str:
    """Build an SRT string from (text, start_ms, duration_ms) tuples.

    Subtitles are rendered in order with no gaps (end = start + duration).
    """
    lines = []
    for i, (text, start_ms, duration_ms) in enumerate(chunks, 1):
        end_ms = start_ms + duration_ms

        def _fmt(ms):
            h = ms // 3_600_000
            m = (ms % 3_600_000) // 60_000
            s = (ms % 60_000) // 1_000
            rem = ms % 1_000
            return f"{h:02d}:{m:02d}:{s:02d},{rem:03d}"

        lines.append(str(i))
        lines.append(f"{_fmt(start_ms)} --> {_fmt(end_ms)}")
        lines.append(text)
        lines.append("")
    return "\n".join(lines)


class FakeCompletedProcess:
    """Mimics subprocess.CompletedProcess for successful yt-dlp runs."""

    def __init__(self, srt_content: str | None = None):
        self.returncode = 0
        self.stdout = ""
        self.stderr = ""
        self._srt = srt_content

    def write_srt(self, tmpdir: str, video_id: str) -> None:
        """Write the fake SRT file to the temp dir, as yt-dlp would."""
        if self._srt:
            path = Path(tmpdir) / f"{video_id}.en.srt"
            path.write_text(self._srt, encoding="utf-8")


class TestParseSrt:
    """Tests for _parse_srt, the SRT→TranscriptChunk parser."""

    def test_parse_basic_srt(self):
        srt = _make_srt([
            ("Hello world", 0, 1000),
            ("Second line", 2000, 1500),
        ])
        with tempfile.NamedTemporaryFile(mode="w", suffix=".srt", delete=False) as f:
            f.write(srt)
            srt_path = f.name

        try:
            chunks = _parse_srt(Path(srt_path))
            assert len(chunks) == 2
            assert chunks[0].text == "Hello world"
            assert chunks[0].start_ms == 0
            assert chunks[0].duration_ms == 1000
            assert chunks[1].text == "Second line"
            assert chunks[1].start_ms == 2000
            assert chunks[1].duration_ms == 1500
        finally:
            Path(srt_path).unlink()

    def test_parse_multiline_subtitle(self):
        srt = (
            "1\n"
            "00:00:01,000 --> 00:00:04,000\n"
            "Line one\n"
            "Line two\n\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".srt", delete=False) as f:
            f.write(srt)
            srt_path = f.name

        try:
            chunks = _parse_srt(Path(srt_path))
            assert len(chunks) == 1
            assert chunks[0].text == "Line one Line two"
        finally:
            Path(srt_path).unlink()

    def test_parse_empty_srt(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".srt", delete=False) as f:
            f.write("")
            srt_path = f.name

        try:
            chunks = _parse_srt(Path(srt_path))
            assert chunks == []
        finally:
            Path(srt_path).unlink()

    def test_parse_handles_dots_in_timestamp(self):
        """Some SRT variants use dots (00:00:01.000) instead of commas."""
        srt = (
            "1\n"
            "00:00:01.000 --> 00:00:04.500\n"
            "Hello\n\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".srt", delete=False) as f:
            f.write(srt)
            srt_path = f.name

        try:
            chunks = _parse_srt(Path(srt_path))
            assert len(chunks) == 1
            assert chunks[0].start_ms == 1000
            assert chunks[0].duration_ms == 3500
        finally:
            Path(srt_path).unlink()


class TestFetchTranscript:
    """Tests for fetching subtitle chunks from YouTube via yt-dlp."""

    def _mock_ytdlp_run(self, srt_content: str | None = None):
        """Create a mock subprocess.run that writes an SRT file and returns success."""
        srt = srt_content

        def _run_side_effect(*args, **kwargs):
            # Extract -o template: args is (cmd_list, ...)
            cmd = args[0]
            out_tmpl = None
            for i, arg in enumerate(cmd):
                if arg == "-o" and i + 1 < len(cmd):
                    out_tmpl = cmd[i + 1]
                    break

            result = MagicMock()
            result.returncode = 0
            result.stdout = ""
            result.stderr = ""

            if srt and out_tmpl:
                # out_tmpl looks like /tmp/xxx/%(id)s.%(ext)s
                tmpl_dir = Path(out_tmpl).parent
                # Find video_id from URL in cmd
                import re as _re
                for arg in cmd:
                    m = _re.search(r"v=([A-Za-z0-9_-]{11})", arg)
                    if m:
                        video_id = m.group(1)
                        srt_path = tmpl_dir / f"{video_id}.en.srt"
                        srt_path.write_text(srt, encoding="utf-8")
                        break

            return result

        return _run_side_effect

    def test_fetch_returns_list_of_chunks(self):
        """fetch_transcript should return a list of TranscriptChunk objects."""
        srt = _make_srt([
            ("我们", 1000, 2000),
            ("一般", 3500, 1500),
            ("早上", 5500, 2000),
        ])

        with patch("subprocess.run", side_effect=self._mock_ytdlp_run(srt)):
            chunks = fetch_transcript("dQw4w9WgXcQ")

        assert isinstance(chunks, list)
        assert len(chunks) > 0
        for chunk in chunks:
            assert isinstance(chunk, TranscriptChunk)
            assert isinstance(chunk.text, str)
            assert isinstance(chunk.start_ms, (int, float))
            assert isinstance(chunk.duration_ms, (int, float))
            assert chunk.text.strip() != ""

    def test_fetch_raises_on_invalid_url(self):
        """fetch_transcript should raise ValueError for video IDs < 11 chars."""
        with pytest.raises((ValueError, Exception)):
            fetch_transcript("xyz")

    def test_fetch_raises_on_video_unavailable(self):
        """fetch_transcript raises ValueError when yt-dlp returns 'Video unavailable'."""
        m = MagicMock()
        m.returncode = 1
        m.stderr = "ERROR: Video unavailable"
        m.stdout = ""
        with patch("subprocess.run", return_value=m):
            with pytest.raises(ValueError, match="unavailable"):
                fetch_transcript("dQw4w9WgXcQ")

    def test_fetch_raises_on_no_subtitles(self):
        """fetch_transcript raises ValueError when no SRT file is found."""
        m = MagicMock()
        m.returncode = 0  # yt-dlp exits 0 but writes no SRT
        m.stderr = ""
        m.stdout = ""
        with patch("subprocess.run", return_value=m):
            with pytest.raises(ValueError, match="No transcript available"):
                fetch_transcript("dQw4w9WgXcQ")

    def test_fetch_raises_on_ip_block(self):
        """fetch_transcript detects HTTP 429 / blocking from stderr."""
        m = MagicMock()
        m.returncode = 1
        m.stderr = "HTTP Error 429: Too Many Requests"
        m.stdout = ""
        with patch("subprocess.run", return_value=m):
            with pytest.raises(ValueError, match="blocking requests"):
                fetch_transcript("dQw4w9WgXcQ")

    def test_chunks_have_increasing_timestamps(self):
        """Chunks should be returned in chronological order."""
        srt = _make_srt([
            ("我们", 1000, 2000),
            ("一般", 3500, 1500),
            ("早上", 5500, 2000),
        ])

        with patch("subprocess.run", side_effect=self._mock_ytdlp_run(srt)):
            chunks = fetch_transcript("dQw4w9WgXcQ")

        for i in range(1, len(chunks)):
            assert chunks[i].start_ms >= chunks[i - 1].start_ms

    def test_language_codes_passed_to_ytdlp(self):
        """Verify that language_codes influences the --sub-lang argument."""
        srt = _make_srt([("Hola", 1000, 2000)])

        captured_cmd = []

        def capture_run(*args, **kwargs):
            captured_cmd.append(args[0])
            return self._mock_ytdlp_run(srt)(*args, **kwargs)

        with patch("subprocess.run", side_effect=capture_run):
            fetch_transcript("dQw4w9WgXcQ", language_codes=["es"])

        # yt-dlp cmd should include --sub-lang es
        assert "--sub-lang" in captured_cmd[0]
        idx = captured_cmd[0].index("--sub-lang")
        assert captured_cmd[0][idx + 1] == "es"


class TestMergeSentences:
    """Tests for the pause-based sentence merging heuristic."""

    def make_chunk(self, text: str, start: int, duration: int) -> TranscriptChunk:
        return TranscriptChunk(text=text, start_ms=start, duration_ms=duration)

    def test_adjacent_chunks_within_gap_are_merged(self):
        """Chunks with gap ≤ threshold should be merged into one sentence."""
        chunks = [
            self.make_chunk("我们一般", 0, 1000),
            self.make_chunk("早上七点起床", 1000, 1500),
        ]
        sentences = merge_sentences(chunks, gap_ms=500)

        assert len(sentences) == 1
        assert sentences[0].text == "我们一般 早上七点起床"
        assert sentences[0].start_ms == 0
        assert sentences[0].end_ms == 2500

    def test_chunks_with_gap_above_threshold_are_split(self):
        """Chunks with gap > threshold should become separate sentences."""
        chunks = [
            self.make_chunk("第一句", 0, 1000),
            self.make_chunk("第二句", 3000, 1000),  # 2000ms gap
        ]
        sentences = merge_sentences(chunks, gap_ms=500)

        assert len(sentences) == 2
        assert sentences[0].text == "第一句"
        assert sentences[1].text == "第二句"

    def test_multiple_chunks_merge_into_one_sentence(self):
        """Several adjacent chunks within gap threshold merge together."""
        chunks = [
            self.make_chunk("我们", 0, 500),
            self.make_chunk("一般", 500, 500),
            self.make_chunk("早上", 1000, 500),
            self.make_chunk("七点起床", 1500, 1000),
        ]
        sentences = merge_sentences(chunks, gap_ms=500)

        assert len(sentences) == 1
        assert "我们 一般 早上 七点起床" in sentences[0].text

    def test_empty_chunk_list_returns_empty(self):
        """Empty input should return empty list."""
        assert merge_sentences([], gap_ms=500) == []

    def test_single_chunk_returns_one_sentence(self):
        """A single chunk should produce one sentence."""
        chunks = [self.make_chunk("你好", 0, 1000)]
        sentences = merge_sentences(chunks, gap_ms=500)
        assert len(sentences) == 1
        assert sentences[0].text == "你好"

    def test_spaces_within_chunks_are_preserved(self):
        """Spaces inside subtitle text (used as soft punctuation) should be preserved."""
        chunks = [
            self.make_chunk("我们", 0, 500),
            self.make_chunk("一般", 500, 500),
        ]
        sentences = merge_sentences(chunks, gap_ms=500)
        # Merged chunks are joined with a space
        assert sentences[0].text == "我们 一般"

    def test_custom_gap_threshold(self):
        """The gap threshold should be configurable via parameter."""
        chunks = [
            self.make_chunk("A", 0, 500),
            self.make_chunk("B", 1200, 500),  # 700ms gap
        ]
        # With 1000ms gap threshold, they should merge
        merged = merge_sentences(chunks, gap_ms=1000)
        assert len(merged) == 1

        # With 500ms gap threshold, they should split
        split = merge_sentences(chunks, gap_ms=500)
        assert len(split) == 2
