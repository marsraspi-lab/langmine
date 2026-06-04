"""Route blueprints — one per resource group.

Each module defines a ``Blueprint`` with its routes.  ``register_routes()``
imports and mounts them all on the Flask app.
"""

from flask import Flask

# Re-export shared helpers so existing callers don't need to know about
# the _helpers module (backwards compatibility with old routes.py layout).
from langmine.web.routes._helpers import (  # noqa: F401
    EDITABLE_FIELDS,
    VALID_SENTENCE_STATUSES,
    _find_sentence,
    _get_audio_processor,
    _get_classifier,
    _get_image_searcher,
    _get_language_code,
    _get_persistence,
    _get_processor,
    _get_sentence_or_404,
    _get_transcript_source,
    _reclassify_from_segmented,
    _sentence_to_dict,
    _unknown_word_dict,
    _video_with_counts,
    _vocab_to_dict,
    _words_array,
)


def register_routes(app: Flask):
    """Register all API and page routes on the Flask app."""
    from langmine.web.routes.config import config_bp
    from langmine.web.routes.export import export_bp
    from langmine.web.routes.images import images_bp
    from langmine.web.routes.sentences import sentences_bp
    from langmine.web.routes.videos import videos_bp
    from langmine.web.routes.vocab import vocab_bp

    app.register_blueprint(config_bp)
    app.register_blueprint(videos_bp)
    app.register_blueprint(sentences_bp)
    app.register_blueprint(vocab_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(images_bp)
