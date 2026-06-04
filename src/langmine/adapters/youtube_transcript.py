"""YouTube Transcript adapter — wraps transcript.py behind TranscriptSource port."""

import subprocess

from langmine.domain.ports import SubtitleInfo, TranscriptChunk, TranscriptSource
from langmine.transcript import fetch_transcript


class YouTubeTranscriptAdapter(TranscriptSource):
    """Fetches subtitles from YouTube via yt-dlp --write-sub."""

    def __init__(self, user_agent: str = "", language_codes: list[str] | None = None):
        self._user_agent = user_agent
        self._language_codes = language_codes or []

    def fetch(self, video_id: str, language: str = "") -> list[TranscriptChunk]:
        lang_codes = [language] if language else self._language_codes
        return fetch_transcript(
            video_id, user_agent=self._user_agent, language_codes=lang_codes
        )

    def list_subtitles(self, video_id: str) -> list[SubtitleInfo]:
        """List available subtitle tracks via yt-dlp --list-subs."""
        from langmine.transcript import _parse_list_subs_output

        url = f"https://www.youtube.com/watch?v={video_id}"
        cmd = [
            "yt-dlp",
            "--list-subs",
            "--skip-download",
            "--no-playlist",
            "--no-warnings",
        ]
        if self._user_agent:
            cmd.insert(1, "--user-agent")
            cmd.insert(2, self._user_agent)
        cmd.append(url)

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        stderr = result.stderr.lower() if result.stderr else ""

        if result.returncode != 0:
            if "video unavailable" in stderr or "private video" in stderr:
                raise ValueError(f"Video '{video_id}' is unavailable or private.")
            return []  # Unknown error, treat as no subtitles

        return _parse_list_subs_output(result.stdout)
