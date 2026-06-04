"""Tests for language_factory.py — language-agnostic processor creation."""

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
    """Factory raises ValueError for unknown language codes not in the plan."""
    from langmine.language_factory import create_language_processor

    config = Config()
    config.source_language = "jp"  # Japanese — not a planned extension

    with pytest.raises(ValueError, match="Unsupported source language"):
        create_language_processor(
            config,
            translator=FakeTranslator(),
            dictionary=FakeDictionary(),
            frequency=FakeFrequency(),
        )


def test_create_processor_for_planned_language_raises_not_implemented():
    """Factory raises NotImplementedError for planned-but-not-yet languages."""
    from langmine.language_factory import create_language_processor

    config = Config()
    config.source_language = "es"

    with pytest.raises(NotImplementedError, match="not yet implemented"):
        create_language_processor(
            config,
            translator=FakeTranslator(),
            dictionary=FakeDictionary(),
            frequency=FakeFrequency(),
        )


def test_spanish_korean_russian_all_raise_not_implemented():
    """Placeholder languages all raise NotImplementedError."""
    from langmine.language_factory import create_language_processor

    for lang in ("es", "ko", "ru"):
        config = Config()
        config.source_language = lang
        with pytest.raises(NotImplementedError, match="not yet implemented"):
            create_language_processor(
                config,
                translator=FakeTranslator(),
                dictionary=FakeDictionary(),
                frequency=FakeFrequency(),
            )
