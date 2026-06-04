"""Tests for subtitle file parsing (SRT and VTT)."""

from langmine.domain.ports import TranscriptChunk
from langmine.transcript_parser import _parse_srt, _parse_vtt, parse_subtitle_file


class TestParseSRT:
    def test_basic_srt(self):
        content = """1
00:00:01,000 --> 00:00:04,500
Hello world

2
00:00:05,000 --> 00:00:08,200
This is a test
"""
        chunks = _parse_srt(content)
        assert len(chunks) == 2
        assert chunks[0].text == "Hello world"
        assert chunks[0].start_ms == 1000
        assert chunks[0].duration_ms == 3500
        assert chunks[1].text == "This is a test"
        assert chunks[1].start_ms == 5000
        assert chunks[1].duration_ms == 3200

    def test_srt_with_html_tags(self):
        """HTML tags should be stripped (YouTube downloads sometimes include them)."""
        content = """1
00:00:01,000 --> 00:00:04,000
<c>Hello</c> <i>world</i>
"""
        chunks = _parse_srt(content)
        assert chunks[0].text == "Hello world"

    def test_srt_with_multiline_text(self):
        content = """1
00:00:01,000 --> 00:00:03,000
Line one
Line two
"""
        chunks = _parse_srt(content)
        assert chunks[0].text == "Line one Line two"

    def test_empty_srt(self):
        assert _parse_srt("") == []
        assert _parse_srt("\n\n") == []

    def test_filename_routing(self):
        """parse_subtitle_file should detect format by extension."""
        srt_content = "1\n00:00:01,000 --> 00:00:02,000\nTest\n"
        vtt_content = "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nTest\n"

        assert len(parse_subtitle_file(srt_content, filename="test.srt")) == 1
        assert len(parse_subtitle_file(vtt_content, filename="test.vtt")) == 1
        # No extension, starts with WEBVTT -> VTT
        assert len(parse_subtitle_file(vtt_content)) == 1
        # No extension, no WEBVTT -> falls back to SRT
        assert len(parse_subtitle_file(srt_content)) == 1


class TestParseVTT:
    def test_basic_vtt(self):
        content = """WEBVTT

00:00:01.000 --> 00:00:04.500
Hello world

00:00:05.000 --> 00:00:08.200
This is a test
"""
        chunks = _parse_vtt(content)
        assert len(chunks) == 2
        assert chunks[0].text == "Hello world"
        assert chunks[0].start_ms == 1000
        assert chunks[0].duration_ms == 3500

    def test_vtt_with_header_metadata(self):
        """VTT files can have metadata lines before timestamps."""
        content = """WEBVTT
Kind: captions
Language: zh

00:00:01.000 --> 00:00:04.000
Test
"""
        chunks = _parse_vtt(content)
        assert len(chunks) == 1
        assert chunks[0].text == "Test"

    def test_empty_vtt(self):
        assert _parse_vtt("WEBVTT\n\n") == []

    def test_timestamp_with_comma(self):
        """YT-DLP sometimes exports VTT with commas instead of periods."""
        content = """WEBVTT

00:00:01,000 --> 00:00:02,500
Test
"""
        chunks = _parse_vtt(content)
        assert len(chunks) == 1
        assert chunks[0].start_ms == 1000
        assert chunks[0].duration_ms == 1500


class TestParseSubtitleFileIntegration:
    def test_chunks_are_valid_transcriptchunks(self):
        content = """1
00:00:01,000 --> 00:00:03,000
你好世界
"""
        chunks = parse_subtitle_file(content, filename="test.srt")
        for chunk in chunks:
            assert isinstance(chunk, TranscriptChunk)
            assert isinstance(chunk.text, str)
            assert isinstance(chunk.start_ms, int | float)
            assert isinstance(chunk.duration_ms, int | float)
            assert chunk.text.strip() != ""
