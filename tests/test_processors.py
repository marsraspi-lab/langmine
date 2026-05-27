"""Tests for the LanguageProcessor plugin interface."""

import pytest

from langmine.processors import LanguageProcessor, ChineseProcessor, get_processor


class DummyProcessor(LanguageProcessor):
    """Minimal implementation for testing the interface."""

    def segment(self, text: str) -> list[str]:
        return text.split()

    def get_reading(self, text: str) -> str:
        return text.lower()

    def lookup_word(self, word: str) -> dict | None:
        return {"definition_de": "test", "definition_en": "test"}

    def translate_sentence(self, text: str) -> str:
        return f"translated: {text}"

    def get_frequency(self, word: str) -> int | None:
        return 1000

    def is_non_word(self, token: str) -> bool:
        return token in {"the", "a", "is"}

    def find_known_synonyms(self, word: str, known_words: set[str]) -> list[str]:
        return []


def test_abstract_class_cannot_be_instantiated():
    """LanguageProcessor is abstract and cannot be instantiated directly."""
    with pytest.raises(TypeError):
        LanguageProcessor()  # type: ignore[abstract]


def test_concrete_implementation_works():
    """A full implementation should work without errors."""
    proc = DummyProcessor()
    assert proc.segment("hello world") == ["hello", "world"]
    assert proc.get_reading("HELLO") == "hello"
    assert proc.translate_sentence("hi") == "translated: hi"
    assert proc.get_frequency("word") == 1000
    assert proc.is_non_word("the") is True
    assert proc.is_non_word("cat") is False


def test_get_processor_returns_chinese_for_zh():
    """get_processor('zh') should return a ChineseProcessor instance."""
    proc = get_processor("zh")
    assert isinstance(proc, ChineseProcessor)
    assert isinstance(proc, LanguageProcessor)


def test_get_processor_raises_for_unknown_language():
    """get_processor with an unregistered language should raise ValueError."""
    with pytest.raises(ValueError, match="No processor registered"):
        get_processor("zz")


def test_chinese_processor_has_all_methods():
    """ChineseProcessor should implement all abstract methods."""
    proc = ChineseProcessor()
    # Methods should exist and be callable with basic inputs
    assert callable(proc.segment)
    assert callable(proc.get_reading)
    assert callable(proc.lookup_word)
    assert callable(proc.translate_sentence)
    assert callable(proc.get_frequency)
    assert callable(proc.is_non_word)
    assert callable(proc.find_known_synonyms)
