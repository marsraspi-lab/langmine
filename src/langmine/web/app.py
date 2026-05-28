"""Flask app factory for LangMine.

Creates a Flask app with domain ports injected — testable with fake adapters.
Serves the Svelte frontend built output from ../static/.
"""

import os
from flask import Flask, send_from_directory

from langmine.domain.ports import (
    Persistence,
    LanguageProcessor,
    TranscriptSource,
    AudioProcessor,
)


def create_app(
    persistence: Persistence,
    language_processor: LanguageProcessor | None = None,
    transcript_source: TranscriptSource | None = None,
    audio_processor: AudioProcessor | None = None,
) -> Flask:
    """Create a Flask app with injected domain ports.

    Args:
        persistence: Where to read/write data (SQLite, fake, etc.)
        language_processor: NLP port (optional for API-only operations)
        transcript_source: Where to fetch subtitles (YouTube, etc.)
        audio_processor: Where to download/clip audio (yt-dlp, etc.)

    Returns:
        Configured Flask app.
    """
    # static_folder points to the Svelte build output
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    app = Flask(__name__, static_folder=static_dir, static_url_path="")

    app.config["LANGMINE_PERSISTENCE"] = persistence
    app.config["LANGMINE_LANGUAGE_PROCESSOR"] = language_processor
    app.config["LANGMINE_TRANSCRIPT_SOURCE"] = transcript_source
    app.config["LANGMINE_AUDIO_PROCESSOR"] = audio_processor

    # Register routes
    from langmine.web.routes import register_routes
    register_routes(app)

    return app
