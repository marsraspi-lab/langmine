"""Configuration management for LangMine."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Config:
    """LangMine configuration with sensible defaults."""

    # Anki
    anki_connect_url: str = "http://localhost:8765"
    deck_name: str = "Chinese::Sentence Mining"
    note_type: str = "LangMine Sentence"
    card_css: str = (
        ".card { font-family: Arial, sans-serif; font-size: 20px; "
        "text-align: center; color: black; background-color: white; }"
        ".chinese { font-size: 28px; margin: 20px 0; }"
        ".pinyin { color: #2e7d32; font-style: italic; margin: 10px 0; }"
        ".translation { font-size: 22px; margin: 10px 0; }"
        ".word { color: #e53935; font-size: 18px; margin-top: 16px; }"
        ".screenshot { margin-top: 16px; }"
        ".screenshot img { max-width: 100%; border-radius: 4px; }"
    )
    card_front_template: str = (
        '<div class="chinese">{{sentence_zh}}</div>'
        "{{#audio}}{{audio}}{{/audio}}"
    )
    card_back_template: str = (
        '<div class="chinese">{{sentence_zh}}</div>'
        "{{#audio}}{{audio}}{{/audio}}"
        '<hr id="answer">'
        '<div class="pinyin">{{sentence_pinyin}}</div>'
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
    sentence_gap_ms: int = 500
    audio_pad_before_ms: int = 250
    audio_pad_after_ms: int = 300
    max_cards_per_video: int = 20
    max_stash_cards: int = 20

    # Vocab
    hsk_bootstrap: int = 3


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
        "vocab": {
            "hsk_bootstrap": config.hsk_bootstrap,
        },
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
        source_language=data["languages"]["source"],
        target_language=data["languages"]["target"],
        translation_api=data["nlp"]["translation_api"],
        deepl_api_key=data["nlp"]["deepl_api_key"],
        sentence_gap_ms=data["mining"]["sentence_gap_ms"],
        audio_pad_before_ms=data["mining"]["audio_pad_before_ms"],
        audio_pad_after_ms=data["mining"]["audio_pad_after_ms"],
        max_cards_per_video=data["mining"]["max_cards_per_video"],
        max_stash_cards=data["mining"]["max_stash_cards"],
        hsk_bootstrap=data["vocab"]["hsk_bootstrap"],
    )
