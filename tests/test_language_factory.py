"""Tests for language_factory.py — language-agnostic processor creation."""

import pytest

from langmine.config import Config
from langmine.domain.ports import LanguageProcessor


def test_create_processor_for_chinese():
    """Factory returns ChineseLanguageService when source_language is 'zh'."""
    from langmine.language_factory import create_language_processor

    config = Config()
    config.source_language = "zh"

    processor = create_language_processor(config)

    from langmine.languages.chinese import ChineseLanguageService
    assert isinstance(processor, ChineseLanguageService)
    assert isinstance(processor, LanguageProcessor)


def test_create_processor_for_unknown_language_raises():
    """Factory raises ValueError for unknown language codes not in the plan."""
    from langmine.language_factory import create_language_processor

    config = Config()
    config.source_language = "jp"  # Japanese — not a planned extension

    with pytest.raises(ValueError, match="Unsupported source language"):
        create_language_processor(config)


def test_create_processor_for_planned_language_raises_not_implemented():
    """Factory raises NotImplementedError for planned-but-not-yet languages."""
    from langmine.language_factory import create_language_processor

    config = Config()
    config.source_language = "es"

    with pytest.raises(NotImplementedError, match="not yet implemented"):
        create_language_processor(config)


def test_spanish_korean_russian_all_raise_not_implemented():
    """Placeholder languages all raise NotImplementedError."""
    from langmine.language_factory import create_language_processor

    for lang in ("es", "ko", "ru"):
        config = Config()
        config.source_language = lang
        with pytest.raises(NotImplementedError, match="not yet implemented"):
            create_language_processor(config)
