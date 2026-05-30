"""Tests for ChineseLanguageService — the Chinese-specific domain service.

All external dependencies (dictionary, translator, frequency data) are
injected as ports, so these tests use fake adapters with zero I/O.
"""

import pytest

from langmine.domain.ports import (
    LanguageProcessor,
    Dictionary,
    Translator,
    FrequencySource,
)
from langmine.languages.chinese import ChineseLanguageService


# === Fake Ports ===


class FakeDictionary(Dictionary):
    """In-memory dictionary for testing."""

    def __init__(self, entries: dict[str, dict] | None = None):
        self._entries = entries or {}

    def lookup(self, word: str) -> dict | None:
        return self._entries.get(word)


class FakeTranslator(Translator):
    """Returns predictable translations."""

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        return f"[DE] {text}"


class FakeFrequency(FrequencySource):
    """Returns fixed frequency ranks."""

    def __init__(self, ranks: dict[str, int] | None = None):
        self._ranks = ranks or {}

    def get_frequency(self, word: str) -> int | None:
        return self._ranks.get(word)


# === Tests ===


def test_chinese_language_service_is_a_language_processor():
    """ChineseLanguageService implements the LanguageProcessor port."""
    svc = ChineseLanguageService(
        dictionary=FakeDictionary(),
        translator=FakeTranslator(),
        frequency=FakeFrequency(),
    )
    assert isinstance(svc, LanguageProcessor)


def test_segment_uses_jieba():
    """segment() should use jieba to split Chinese text."""
    svc = ChineseLanguageService(FakeDictionary(), FakeTranslator(), FakeFrequency())

    result = svc.segment("我们一般早上七点起床")
    assert len(result) >= 3  # Should segment into multiple words
    assert "我们" in result or "我" in result


def test_get_reading_returns_pinyin():
    """get_reading() should return pinyin for Chinese text."""
    svc = ChineseLanguageService(FakeDictionary(), FakeTranslator(), FakeFrequency())

    reading = svc.get_reading("你好")
    assert len(reading) > 0
    # pypinyin returns space-separated pinyin
    assert "ni" in reading.lower() or "hao" in reading.lower()


def test_is_non_word_filters_particles():
    """is_non_word() should return True for particles like 的, 了, 吗."""
    svc = ChineseLanguageService(FakeDictionary(), FakeTranslator(), FakeFrequency())

    assert svc.is_non_word("的") is True
    assert svc.is_non_word("了") is True
    assert svc.is_non_word("吗") is True
    assert svc.is_non_word("吧") is True
    assert svc.is_non_word("呢") is True
    assert svc.is_non_word("啊") is True


def test_is_non_word_filters_numbers():
    """is_non_word() should return True for pure numbers."""
    svc = ChineseLanguageService(FakeDictionary(), FakeTranslator(), FakeFrequency())

    assert svc.is_non_word("123") is True
    assert svc.is_non_word("七") is True      # standalone number
    assert svc.is_non_word("2024年") is True  # year


def test_is_non_word_returns_false_for_content_words():
    """is_non_word() should return False for real content words."""
    svc = ChineseLanguageService(FakeDictionary(), FakeTranslator(), FakeFrequency())

    assert svc.is_non_word("学习") is False
    assert svc.is_non_word("我们") is False
    assert svc.is_non_word("早上") is False


def test_lookup_word_delegates_to_dictionary_port():
    """lookup_word() should call the Dictionary port, not CC-CEDICT directly."""
    dictionary = FakeDictionary({
        "学习": {"definition_de": "lernen", "definition_en": "to study", "pinyin": "xué xí"},
    })
    svc = ChineseLanguageService(dictionary, FakeTranslator(), FakeFrequency())

    result = svc.lookup_word("学习")
    assert result is not None
    assert result["definition_de"] == "lernen"

    # Unknown word
    assert svc.lookup_word("不存在的词") is None


def test_translate_sentence_delegates_to_translator_port():
    """translate_sentence() should call Translator port, not Google directly."""
    svc = ChineseLanguageService(FakeDictionary(), FakeTranslator(), FakeFrequency())

    result = svc.translate_sentence("你好世界")
    assert result == "[DE] 你好世界"


def test_get_frequency_delegates_to_frequency_port():
    """get_frequency() should call FrequencySource port, not SUBTLEX-CH directly."""
    frequency = FakeFrequency({"学习": 500, "一般": 2000})
    svc = ChineseLanguageService(FakeDictionary(), FakeTranslator(), frequency)

    assert svc.get_frequency("学习") == 500
    assert svc.get_frequency("一般") == 2000
    assert svc.get_frequency("unknown") is None


def test_find_known_synonyms_detects_from_dictionary():
    """find_known_synonyms() should use Dictionary port to find synonyms."""
    dictionary = FakeDictionary({
        "常常": {
            "definition_de": "oft",
            "definition_en": "often / same as 经常",
            "pinyin": "cháng cháng",
        },
        "经常": {
            "definition_de": "oft",
            "definition_en": "often",
            "pinyin": "jīng cháng",
        },
    })
    svc = ChineseLanguageService(dictionary, FakeTranslator(), FakeFrequency())

    synonyms = svc.find_known_synonyms("常常", known_words={"经常", "学习"})
    assert "经常" in synonyms


def test_find_known_synonyms_returns_empty_for_no_match():
    """Should return empty list when no known synonyms found."""
    svc = ChineseLanguageService(FakeDictionary(), FakeTranslator(), FakeFrequency())

    synonyms = svc.find_known_synonyms("随便", known_words=set())
    assert synonyms == []


def test_no_network_calls_in_pure_methods():
    """segment, get_reading, is_non_word should work without any ports set up."""
    # Even with no ports, pure methods should work
    svc = ChineseLanguageService(FakeDictionary(), FakeTranslator(), FakeFrequency())

    # These are pure in-memory operations
    assert len(svc.segment("你好世界")) >= 2
    assert len(svc.get_reading("你好")) > 0
    assert svc.is_non_word("的") is True
