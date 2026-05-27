"""Tests for the LanguageProcessor port (in ports.py) and compat shim."""

import pytest

from langmine.domain.ports import LanguageProcessor
from langmine.processors import get_processor


class DummyProcessor(LanguageProcessor):
    """Minimal implementation for testing the port interface."""

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


def test_language_processor_is_in_domain_ports():
    """LanguageProcessor should live in domain.ports, not processors.py."""
    from langmine.domain import ports as ports_module
    assert hasattr(ports_module, "LanguageProcessor")
    assert ports_module.LanguageProcessor is LanguageProcessor


def test_get_processor_raises_for_unknown_language():
    """get_processor with an unregistered language should raise ValueError."""
    with pytest.raises(ValueError, match="No processor"):
        get_processor("zz")


def test_get_processor_zh_raises_not_implemented():
    """Chinese adapter wiring is not yet implemented — M2/M4."""
    with pytest.raises(NotImplementedError):
        get_processor("zh")
