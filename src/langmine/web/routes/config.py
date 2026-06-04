"""Config, stats, and system API routes."""

import os
from importlib.metadata import version as _pkg_version

from flask import Blueprint, current_app, jsonify, request, send_from_directory

from ._helpers import _get_language_code, _get_persistence

config_bp = Blueprint("config", __name__)


@config_bp.route("/")
def index():
    """Serve the Svelte SPA."""
    static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
    return send_from_directory(static_dir, "index.html")


# === API Routes ===


@config_bp.route("/api/version")
def app_version():
    """Return the installed LangMine version."""
    try:
        v = _pkg_version("langmine")
    except Exception:
        v = "unknown"
    return jsonify({"version": v, "name": "langmine"})


@config_bp.route("/api/languages")
def list_languages():
    """List available source languages with code, display name, and settings schema."""
    from langmine.language_factory import (
        get_available_languages,
        get_language_settings_schema,
    )

    languages = get_available_languages()
    for lang in languages:
        lang["settings_schema"] = get_language_settings_schema(lang["code"])
    return jsonify({"languages": languages})


@config_bp.route("/api/stats")
def stats():
    """Return vocabulary stats."""
    persistence = _get_persistence()
    lang = _get_language_code()
    return jsonify(persistence.get_vocab_stats(language_code=lang))


@config_bp.route("/api/config")
def get_config():
    """Return current configuration (sanitized — no API keys)."""
    config = current_app.config["LANGMINE_CONFIG"]
    return jsonify(
        {
            "anki_connect_url": config.anki_connect_url,
            "source_language": config.source_language,
            "target_language": config.target_language,
            "translation_api": config.translation_api,
            "sentence_gap_ms": config.sentence_gap_ms,
            "audio_pad_before_ms": config.audio_pad_before_ms,
            "audio_pad_after_ms": config.audio_pad_after_ms,
            "max_cards_per_video": config.max_cards_per_video,
            "max_stash_cards": config.max_stash_cards,
            "language_settings": config.language_settings,
            "user_agent": config.user_agent,
        }
    )


@config_bp.route("/api/config", methods=["PUT"])
def update_config():
    """Update configuration and save to config.yaml."""
    from langmine.config import save_config

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Missing request body"}), 400

    # Allowed config keys
    ALLOWED = {
        "anki_connect_url",
        "source_language",
        "target_language",
        "translation_api",
        "sentence_gap_ms",
        "audio_pad_before_ms",
        "audio_pad_after_ms",
        "max_cards_per_video",
        "max_stash_cards",
        "deepl_api_key",
        "user_agent",
        "language_settings",
    }

    config = current_app.config["LANGMINE_CONFIG"]
    config_dir = current_app.config.get("LANGMINE_CONFIG_DIR")
    for key, value in data.items():
        if key == "language_settings":
            # Deep-merge per-language settings
            for lang_code, settings in value.items():
                config.language_settings.setdefault(lang_code, {}).update(settings)
        elif key in ALLOWED:
            setattr(config, key, value)

    try:
        save_config(config, config_dir=config_dir)
    except Exception as e:
        return jsonify({"error": f"Failed to save config: {e}"}), 500

    return jsonify({"ok": True})
