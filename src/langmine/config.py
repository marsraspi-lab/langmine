"""Configuration management — YAML-backed settings for LangMine.

Defines the Config dataclass (all tunables with defaults), loads from
~/.langmine/config.yaml (merging onto defaults), and saves back.
No dependency on adapters or domain — safe to import from any layer.
"""

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Config:
    """LangMine configuration with sensible defaults."""

    # Anki
    anki_connect_url: str = "http://host.docker.internal:8765"
    deck_name: str = "Chinese::Sentence Mining"
    note_type: str = "LangMine Sentence"
    card_css: str = (
        ".card { font-family: Arial, sans-serif; font-size: 20px; "
        "text-align: center; color: black; background-color: white; }"
        ".chinese { font-size: 28px; margin: 20px 0; }"
        ".reading { color: #2e7d32; font-style: italic; margin: 10px 0; }"
        ".translation { font-size: 22px; margin: 10px 0; }"
        ".word { color: #e53935; font-size: 18px; margin-top: 16px; }"
        ".screenshot { margin-top: 16px; }"
        ".screenshot img { max-width: 100%; border-radius: 4px; }"
    )
    card_front_template: str = (
        '<div class="chinese">{{sentence_zh}}</div>{{#audio}}{{audio}}{{/audio}}'
    )
    card_back_template: str = (
        '<div class="chinese">{{sentence_zh}}</div>'
        "{{#audio}}{{audio}}{{/audio}}"
        '<hr id="answer">'
        '<div class="reading">{{sentence_reading}}</div>'
        '<div class="translation">{{translation_de}}</div>'
        "{{#unknown_word}}"
        '<div class="word">🆕 {{unknown_word}}</div>'
        "{{/unknown_word}}"
        "{{#screenshot}}"
        '<div class="screenshot">{{screenshot}}</div>'
        "{{/screenshot}}"
    )

    # Language
    source_language: str = "zh"
    target_language: str = "de"

    # NLP
    translation_api: str = "google"
    deepl_api_key: str = ""

    # Mining
    sentence_gap_ms: int = 0
    audio_pad_before_ms: int = 250
    audio_pad_after_ms: int = 300
    max_cards_per_video: int = 20
    max_stash_cards: int = 20

    # Storage
    data_dir: str = "~/.langmine/data"

    # Cloze
    cloze_note_type: str = "LangMine Cloze"
    cloze_card_css: str = (
        ".card { font-family: Arial, sans-serif; font-size: 20px; }\n"
        ".chinese { font-size: 28px; margin: 20px 0; }\n"
        ".cloze { color: #e53935; font-weight: bold; }\n"
        ".reading { color: #2e7d32; font-style: italic; }\n"
        ".translation { font-size: 22px; }\n"
        ".hint-img { margin-top: 12px; max-width: 100%; }\n"
    )
    cloze_card_front_template: str = (
        '<div class="chinese">{{cloze:sentence_zh}}</div>\n'
        "{{#audio}}{{audio}}{{/audio}}\n"
        '{{#screenshot}}<div class="hint-img">{{screenshot}}</div>{{/screenshot}}\n'
    )
    cloze_card_back_template: str = (
        '<div class="chinese">{{sentence_zh}}</div>\n'
        "{{#audio}}{{audio}}{{/audio}}\n"
        '<hr id="answer">\n'
        '<div class="reading">{{sentence_reading}}</div>\n'
        '<div class="translation">{{translation_de}}</div>\n'
        "<div>🆕 {{unknown_word}}</div>\n"
        '{{#screenshot}}<div class="hint-img">{{screenshot}}</div>{{/screenshot}}\n'
    )

    # Network
    user_agent: str = ""

    # Image search (M12)
    google_api_key: str = ""
    google_cse_id: str = ""

    # Language-specific settings (per-language mining config)
    language_settings: dict[str, dict] = field(default_factory=dict)


def load_config(config_dir: str | None = None) -> Config:
    """Load configuration from a YAML file, with defaults for missing keys.

    Creates the config directory if it doesn't exist.
    """
    if config_dir is None:
        config_dir = str(Path.home() / ".langmine")

    config_path = Path(config_dir)
    config_path.mkdir(parents=True, exist_ok=True)

    defaults = _config_to_dict(Config())

    # Merge YAML on top of defaults if it exists
    yaml_file = config_path / "config.yaml"
    if yaml_file.exists():
        with open(yaml_file) as f:
            yaml_data = yaml.safe_load(f) or {}
        defaults = _deep_merge(defaults, yaml_data)

    return _dict_to_config(defaults)


def _config_to_dict(config: Config) -> dict:
    """Convert Config to a nested dict matching the YAML structure."""
    return {
        "anki": {
            "anki_connect_url": config.anki_connect_url,
            "deck_name": config.deck_name,
            "note_type": config.note_type,
            "card_css": config.card_css,
            "card_front_template": config.card_front_template,
            "card_back_template": config.card_back_template,
            "cloze_note_type": config.cloze_note_type,
            "cloze_card_css": config.cloze_card_css,
            "cloze_card_front_template": config.cloze_card_front_template,
            "cloze_card_back_template": config.cloze_card_back_template,
        },
        "languages": {
            "source": config.source_language,
            "target": config.target_language,
        },
        "nlp": {
            "translation_api": config.translation_api,
            "deepl_api_key": config.deepl_api_key,
        },
        "mining": {
            "sentence_gap_ms": config.sentence_gap_ms,
            "audio_pad_before_ms": config.audio_pad_before_ms,
            "audio_pad_after_ms": config.audio_pad_after_ms,
            "max_cards_per_video": config.max_cards_per_video,
            "max_stash_cards": config.max_stash_cards,
        },
        "storage": {
            "data_dir": config.data_dir,
        },
        "network": {
            "user_agent": config.user_agent,
            "google_api_key": config.google_api_key,
            "google_cse_id": config.google_cse_id,
        },
        "language_settings": config.language_settings,
    }


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _dict_to_config(data: dict) -> Config:
    """Convert a nested dict back to a Config object."""
    return Config(
        anki_connect_url=data["anki"]["anki_connect_url"],
        deck_name=data["anki"]["deck_name"],
        note_type=data["anki"]["note_type"],
        card_css=data["anki"].get("card_css", Config.card_css),
        card_front_template=data["anki"].get(
            "card_front_template", Config.card_front_template
        ),
        card_back_template=data["anki"].get(
            "card_back_template", Config.card_back_template
        ),
        cloze_note_type=data["anki"].get("cloze_note_type", Config.cloze_note_type),
        cloze_card_css=data["anki"].get("cloze_card_css", Config.cloze_card_css),
        cloze_card_front_template=data["anki"].get(
            "cloze_card_front_template", Config.cloze_card_front_template
        ),
        cloze_card_back_template=data["anki"].get(
            "cloze_card_back_template", Config.cloze_card_back_template
        ),
        source_language=data["languages"]["source"],
        target_language=data["languages"]["target"],
        translation_api=data["nlp"]["translation_api"],
        deepl_api_key=data["nlp"]["deepl_api_key"],
        sentence_gap_ms=data["mining"]["sentence_gap_ms"],
        audio_pad_before_ms=data["mining"]["audio_pad_before_ms"],
        audio_pad_after_ms=data["mining"]["audio_pad_after_ms"],
        max_cards_per_video=data["mining"]["max_cards_per_video"],
        max_stash_cards=data["mining"]["max_stash_cards"],
        language_settings=data.get("language_settings", {}),
        data_dir=data.get("storage", {}).get("data_dir", "~/.langmine/data"),
        user_agent=data.get("network", {}).get("user_agent", ""),
        google_api_key=data.get("network", {}).get("google_api_key", ""),
        google_cse_id=data.get("network", {}).get("google_cse_id", ""),
    )


def save_config(config: Config, config_dir: str | None = None) -> None:
    """Save a Config object back to the YAML file.

    Args:
        config: The Config object to save.
        config_dir: Override config directory (defaults to ~/.langmine).
    """
    if config_dir is None:
        config_dir = str(Path.home() / ".langmine")

    config_path = Path(config_dir)
    config_path.mkdir(parents=True, exist_ok=True)

    yaml_file = config_path / "config.yaml"
    data = _config_to_dict(config)
    with open(yaml_file, "w") as f:
        yaml.dump(
            data, f, allow_unicode=True, default_flow_style=False, sort_keys=False
        )
