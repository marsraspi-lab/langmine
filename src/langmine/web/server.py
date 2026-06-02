"""Server entry point for LangMine."""

import argparse
import os
from importlib.metadata import version as _pkg_version

from langmine.config import load_config


def _get_version() -> str:
    """Return the installed package version."""
    try:
        return _pkg_version("langmine")
    except Exception:
        return "unknown"


def main():
    """Start the LangMine Flask web UI with real adapters."""
    parser = argparse.ArgumentParser(
        prog="langmine",
        description="YouTube sentence mining for language learning (Web UI)",
    )
    parser.add_argument("--version", action="version",
                        version=f"langmine {_get_version()}")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on")

    args = parser.parse_args()

    from langmine.web.app import create_app
    from langmine.adapters import (
        YouTubeTranscriptAdapter,
        YtdlpAudioAdapter,
        SQLitePersistence,
        AnkiConnectAdapter,
        GoogleImageSearch,
    )
    from langmine.language_factory import create_language_processor, get_transcript_languages

    config = load_config()
    persistence = SQLitePersistence()
    processor = create_language_processor(config)
    transcript = YouTubeTranscriptAdapter(
        user_agent=config.user_agent,
        language_codes=get_transcript_languages(config.source_language),
    )
    audio = YtdlpAudioAdapter(user_agent=config.user_agent)

    app = create_app(
        persistence=persistence,
        language_processor=processor,
        transcript_source=transcript,
        audio_processor=audio,
        anki_exporter=AnkiConnectAdapter(url=config.anki_connect_url),
        image_searcher=GoogleImageSearch(
            api_key=config.google_api_key,
            cse_id=config.google_cse_id,
        ) if config.google_api_key else None,
    )

    print(f"⛏️  LangMine server starting at http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=True, use_reloader=False)


if __name__ == "__main__":
    main()
