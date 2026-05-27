"""Tests for configuration loading."""

import tempfile
import os
from pathlib import Path

from langmine.config import Config, load_config


def test_default_config_values():
    """Config should return sensible defaults when no file exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = load_config(config_dir=tmpdir)

        assert config.anki_connect_url == "http://localhost:8765"
        assert config.deck_name == "Chinese::Sentence Mining"
        assert config.note_type == "LangMine Sentence"
        assert config.source_language == "zh"
        assert config.target_language == "de"
        assert config.translation_api == "google"
        assert config.sentence_gap_ms == 500
        assert config.audio_pad_before_ms == 250
        assert config.audio_pad_after_ms == 300
        assert config.max_cards_per_video == 20
        assert config.max_stash_cards == 20
        assert config.hsk_bootstrap == 3


def test_config_loaded_from_yaml():
    """Config should load values from a YAML file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.yaml"
        config_path.write_text("""
anki:
  anki_connect_url: "http://localhost:9999"
  deck_name: "Test Deck"

mining:
  sentence_gap_ms: 800
  max_cards_per_video: 10
""")

        config = load_config(config_dir=tmpdir)

        # Overridden values
        assert config.anki_connect_url == "http://localhost:9999"
        assert config.deck_name == "Test Deck"
        assert config.sentence_gap_ms == 800
        assert config.max_cards_per_video == 10

        # Defaults for keys not in the YAML
        assert config.note_type == "LangMine Sentence"
        assert config.source_language == "zh"


def test_data_dir_created_on_first_load():
    """Config loading should create the data directory if it doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir) / "nonexistent" / "langmine"
        assert not data_dir.exists()

        load_config(config_dir=str(data_dir))

        assert data_dir.exists()
        assert data_dir.is_dir()
