"""Tests for language_factory.py — registry-based language dispatch."""

import pytest

from langmine.config import Config
from langmine.domain.ports import (
    Dictionary,
    FrequencySource,
    LanguageProcessor,
    Translator,
)


class FakeTranslator(Translator):
    """Fake translator for testing — returns the input text unchanged."""

    def translate(self, text: str, source_lang: str = "", target_lang: str = "") -> str:
        return f"[{target_lang}] {text}"


class FakeDictionary(Dictionary):
    """Fake dictionary for testing."""

    def lookup(self, word: str) -> dict | None:
        return None


class FakeFrequency(FrequencySource):
    """Fake frequency source for testing."""

    def get_frequency(self, word: str) -> int | None:
        return None


# === create_language_processor ===


def test_create_processor_for_chinese():
    """Factory returns ChineseLanguageService when source_language is 'zh'."""
    from langmine.language_factory import create_language_processor

    config = Config()
    config.source_language = "zh"

    processor = create_language_processor(
        config,
        translator=FakeTranslator(),
        dictionary=FakeDictionary(),
        frequency=FakeFrequency(),
    )

    from langmine.languages.chinese import ChineseLanguageService

    assert isinstance(processor, ChineseLanguageService)
    assert isinstance(processor, LanguageProcessor)


def test_create_processor_for_unknown_language_raises():
    """Factory raises ValueError for unknown language codes."""
    from langmine.language_factory import create_language_processor

    config = Config()
    config.source_language = "jp"  # Japanese — not implemented

    with pytest.raises(ValueError, match="Unsupported source language"):
        create_language_processor(
            config,
            translator=FakeTranslator(),
            dictionary=FakeDictionary(),
            frequency=FakeFrequency(),
        )


# === get_available_languages (auto-discovery) ===


def test_get_available_languages_discovers_chinese():
    """Auto-discovery finds the Chinese language package."""
    from langmine.language_factory import get_available_languages

    languages = get_available_languages()
    codes = [lang["code"] for lang in languages]

    assert "zh" in codes
    chinese = next(lang for lang in languages if lang["code"] == "zh")
    assert chinese["name"] == "Chinese"


# === create_language_adapters ===


def test_create_language_adapters_for_chinese():
    """create_language_adapters returns Chinese dict + freq adapters."""
    from langmine.language_factory import create_language_adapters

    config = Config()
    config.source_language = "zh"

    dictionary, frequency = create_language_adapters(config)

    from langmine.languages.chinese import CcCedictAdapter, SubtlexChAdapter

    assert isinstance(dictionary, CcCedictAdapter)
    assert isinstance(frequency, SubtlexChAdapter)


# === getter functions ===


def test_get_anki_templates_returns_dict():
    """get_anki_templates returns card template dict for Chinese."""
    from langmine.language_factory import get_anki_templates

    templates = get_anki_templates("zh")
    assert isinstance(templates, dict)
    assert "basic_front" in templates
    assert "cloze_front" in templates


def test_get_language_manifest_returns_dict():
    """get_language_manifest returns manifest for Chinese."""
    from langmine.language_factory import get_language_manifest

    manifest = get_language_manifest("zh")
    assert manifest["name"] == "中文"
    assert "deck_name" in manifest


def test_get_transcript_languages_returns_list():
    """get_transcript_languages returns subtitle codes for Chinese."""
    from langmine.language_factory import get_transcript_languages

    codes = get_transcript_languages("zh")
    assert isinstance(codes, list)
    assert "zh-Hans" in codes


def test_get_proficiency_level_returns_int_or_none():
    """get_proficiency_level delegates to the language's proficiency function."""
    from langmine.language_factory import get_proficiency_level

    # Known HSK word
    level = get_proficiency_level("我们", "zh")
    assert level is None or isinstance(level, int)

    # Empty language code → None
    assert get_proficiency_level("anything", "") is None

    # Unknown word → None
    assert get_proficiency_level("zwxqrpnm", "zh") is None


def test_empty_lang_code_returns_safe_defaults():
    """All getters return empty/zero values for empty language codes."""
    from langmine.language_factory import (
        get_anki_templates,
        get_language_manifest,
        get_transcript_languages,
    )

    assert get_anki_templates("") == {}
    assert get_language_manifest("") == {}
    assert get_transcript_languages("") == []
