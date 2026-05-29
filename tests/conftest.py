"""Shared fixtures for LangMine tests."""

import pytest
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import IpBlocked


def _youtube_available() -> bool:
    """Check if YouTube is reachable from this IP."""
    try:
        # Lightweight check — don't actually fetch a full transcript
        api = YouTubeTranscriptApi()
        api.fetch("dQw4w9WgXcQ", languages=["en"])
        return True
    except IpBlocked:
        return False
    except Exception:
        # Other errors (no transcript, etc.) don't mean we're blocked
        return True


@pytest.fixture(scope="session")
def youtube_available() -> bool:
    """True if YouTube is reachable, False if IP-blocked."""
    return _youtube_available()
