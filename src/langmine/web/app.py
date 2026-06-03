"""Flask app factory for LangMine.

Creates a Flask app with domain ports injected — testable with fake adapters.
Serves the Svelte frontend built output from ../static/.

``create_app()`` is the injectable factory used by tests.
``create_production_app()`` wires real adapters and is called by server.py.
"""

import os
from flask import Flask, send_from_directory

from langmine.domain.ports import (
    Persistence,
    LanguageProcessor,
    TranscriptSource,
    AudioProcessor,
    AnkiExporter,
    ImageSearch,
    Translator,
)
from langmine.adapters.inline_transcript import InlineTranscriptSource
from langmine.transcript_parser import parse_subtitle_file


def create_app(
    persistence: Persistence,
    language_processor: LanguageProcessor | None = None,
    transcript_source: TranscriptSource | None = None,
    audio_processor: AudioProcessor | None = None,
    anki_exporter: AnkiExporter | None = None,
    image_searcher: ImageSearch | None = None,
    config = None,
) -> Flask:
    """Create a Flask app with injected domain ports.

    Args:
        persistence: Where to read/write data (SQLite, fake, etc.)
        language_processor: NLP port (optional for API-only operations)
        transcript_source: Where to fetch subtitles (YouTube, etc.)
        audio_processor: Where to download/clip audio (yt-dlp, etc.)
        anki_exporter: Where to export flashcards (AnkiConnect, etc.)
        image_searcher: Image search adapter (Google CSE, etc.)
        config: Application configuration (Config dataclass).

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
    app.config["LANGMINE_ANKI_EXPORTER"] = anki_exporter
    app.config["LANGMINE_IMAGE_SEARCHER"] = image_searcher

    app.config["LANGMINE_CONFIG"] = config

    # Allow routes to create InlineTranscriptSource without importing adapters
    app.config["LANGMINE_INLINE_TRANSCRIPT_CLASS"] = InlineTranscriptSource
    app.config["LANGMINE_PARSE_SUBTITLE_FILE"] = parse_subtitle_file

    # Register routes
    from langmine.web.routes import register_routes
    register_routes(app)

    return app


def _create_translator(config) -> Translator:
    """Resolve a Translator from config.translation_api.

    Add new providers here as they're implemented.
    """
    if config.translation_api == "deepl" and config.deepl_api_key:
        raise NotImplementedError(
            "DeepL adapter not yet implemented. "
            "Set translation_api to 'google' or contribute a DeepL adapter "
            "at langmine.adapters.deepl_translate."
        )
    from langmine.adapters.google_translate import GoogleTranslateAdapter
    return GoogleTranslateAdapter()


def create_production_app() -> Flask:
    """Create a Flask app wired with real production adapters.

    Loads config, instantiates concrete adapters, and returns a fully
    wired app ready to serve.  This is the entry point used by server.py.
    """
    from langmine.config import load_config
    from langmine.adapters import (
        YouTubeTranscriptAdapter,
        YtdlpAudioAdapter,
        SQLitePersistence,
        AnkiConnectAdapter,
        GoogleImageSearch,
    )
    from langmine.language_factory import (
        create_language_processor,
        create_language_adapters,
        get_transcript_languages,
    )

    config = load_config()
    persistence = SQLitePersistence()

    # Cross-cutting ports — wired here, not in language_factory
    translator = _create_translator(config)
    dictionary, frequency = create_language_adapters(config)

    processor = create_language_processor(
        config,
        translator=translator,
        dictionary=dictionary,
        frequency=frequency,
    )
    transcript = YouTubeTranscriptAdapter(
        user_agent=config.user_agent,
        language_codes=get_transcript_languages(config.source_language),
    )
    audio = YtdlpAudioAdapter(user_agent=config.user_agent)

    return create_app(
        persistence=persistence,
        language_processor=processor,
        transcript_source=transcript,
        audio_processor=audio,
        anki_exporter=AnkiConnectAdapter(url=config.anki_connect_url),
        image_searcher=GoogleImageSearch(
            api_key=config.google_api_key,
            cse_id=config.google_cse_id,
        ) if config.google_api_key else None,
        config=config,
    )
