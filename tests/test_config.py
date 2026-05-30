"""Tests for configuration loading."""

import tempfile
import os
from pathlib import Path

from langmine.config import Config, load_config


def test_default_config_values():
    """Config should return sensible defaults when no file exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = load_config(config_dir=tmpdir)

        assert config.anki_connect_url == "http://host.docker.internal:8765"
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


def test_data_dir_default_and_round_trip():
    """Config data_dir should default to ~/.langmine/data and survive YAML round-trip."""
    from langmine.config import save_config

    with tempfile.TemporaryDirectory() as tmpdir:
        # Default value
        config = load_config(config_dir=tmpdir)
        assert config.data_dir == "~/.langmine/data"

        # Override and save
        config.data_dir = "/custom/data/path"
        save_config(config, config_dir=tmpdir)

        # Reload and verify
        config2 = load_config(config_dir=tmpdir)
        assert config2.data_dir == "/custom/data/path"


def test_user_agent_default_and_round_trip():
    """Config user_agent should default to empty and survive YAML round-trip."""
    from langmine.config import save_config

    with tempfile.TemporaryDirectory() as tmpdir:
        # Default is empty string (use library defaults)
        config = load_config(config_dir=tmpdir)
        assert config.user_agent == ""

        # Override and save
        config.user_agent = "Mozilla/5.0 TestAgent"
        save_config(config, config_dir=tmpdir)

        # Reload and verify
        config2 = load_config(config_dir=tmpdir)
        assert config2.user_agent == "Mozilla/5.0 TestAgent"


def test_user_agent_reads_from_network_section():
    """Config should load user_agent from a network: section in YAML."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.yaml"
        config_path.write_text("""
network:
  user_agent: "Mozilla/5.0 Firefox"
""")
        config = load_config(config_dir=tmpdir)
        assert config.user_agent == "Mozilla/5.0 Firefox"
