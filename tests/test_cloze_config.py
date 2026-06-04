"""Tests for M11 cloze deletion export configuration."""

from langmine.config import Config, _config_to_dict, _dict_to_config


class TestClozeConfig:
    """M11: Config dataclass must include cloze export fields."""

    def test_config_has_cloze_fields(self):
        """Default Config has cloze_note_type, cloze_card_css, and templates."""
        cfg = Config()
        assert hasattr(cfg, "cloze_note_type"), "Missing cloze_note_type"
        assert isinstance(cfg.cloze_note_type, str)
        assert cfg.cloze_note_type == "LangMine Cloze"

    def test_cloze_card_css_default(self):
        """Default CSS for cloze cards includes styling classes."""
        cfg = Config()
        assert hasattr(cfg, "cloze_card_css"), "Missing cloze_card_css"
        assert ".card" in cfg.cloze_card_css
        assert ".cloze" in cfg.cloze_card_css
        assert ".chinese" in cfg.cloze_card_css

    def test_cloze_front_template_has_cloze_tag(self):
        """Front template uses {{cloze:sentence_zh}} for deletion."""
        cfg = Config()
        assert hasattr(cfg, "cloze_card_front_template")
        assert "{{cloze:sentence_zh}}" in cfg.cloze_card_front_template

    def test_cloze_back_template_has_answer_fields(self):
        """Back template shows pinyin, translation, unknown word."""
        cfg = Config()
        assert hasattr(cfg, "cloze_card_back_template")
        assert "{{sentence_reading}}" in cfg.cloze_card_back_template
        assert "{{translation}}" in cfg.cloze_card_back_template

    def test_cloze_roundtrip_through_dict(self):
        """Cloze fields survive config_to_dict → dict_to_config roundtrip."""
        cfg = Config()
        d = _config_to_dict(cfg)
        restored = _dict_to_config(d)
        assert restored.cloze_note_type == cfg.cloze_note_type
        assert restored.cloze_card_css == cfg.cloze_card_css
        assert restored.cloze_card_front_template == cfg.cloze_card_front_template
        assert restored.cloze_card_back_template == cfg.cloze_card_back_template


class TestConfigApiAllowed:
    """M11: PUT /api/config must allow cloze fields."""

    def test_allowed_fields_include_cloze(self):
        """The ALLOWED set used by routes.py includes cloze config keys."""
        from langmine.config import Config, _config_to_dict

        cfg = Config()
        d = _config_to_dict(cfg)

        # Cloze fields are nested under 'anki' in the YAML structure
        anki = d["anki"]
        assert "cloze_note_type" in anki, (
            "cloze_note_type must be under anki in config dict"
        )
        assert "cloze_card_css" in anki
        assert "cloze_card_front_template" in anki
        assert "cloze_card_back_template" in anki
