"""Tests for real adapters: GoogleTranslateAdapter, CcCedictAdapter, JiebaFrequencyAdapter.

These tests validate the adapter contracts — they implement the domain ports
correctly and produce expected output shapes.
"""

import pytest

from langmine.domain.ports import Translator, Dictionary, FrequencySource


# === GoogleTranslateAdapter ===


class TestGoogleTranslateAdapter:
    """Tests for GoogleTranslateAdapter using deep-translator.

    Network calls to Google Translate are mocked so the test suite
    runs reliably in CI without hitting rate limits.
    """

    def test_implements_translator_port(self):
        """Adapter should implement the Translator port."""
        from langmine.adapters.google_translate import GoogleTranslateAdapter
        adapter = GoogleTranslateAdapter()
        assert isinstance(adapter, Translator)

    def test_translate_zh_to_de(self):
        """Should translate simple Chinese to German."""
        from unittest.mock import patch, MagicMock
        from langmine.adapters.google_translate import GoogleTranslateAdapter

        # Mock deep_translator.GoogleTranslator to avoid real HTTP calls
        mock_translator = MagicMock()
        mock_translator.translate.return_value = "Hallo"

        with patch("deep_translator.GoogleTranslator", return_value=mock_translator):
            adapter = GoogleTranslateAdapter()
            result = adapter.translate("你好", source_lang="zh", target_lang="de")

        assert isinstance(result, str)
        assert len(result) > 0
        assert result != "你好"

    def test_translate_returns_string_for_empty_input(self):
        """Should handle empty input gracefully (no network call needed)."""
        from langmine.adapters.google_translate import GoogleTranslateAdapter
        adapter = GoogleTranslateAdapter()
        result = adapter.translate("", source_lang="zh", target_lang="de")
        assert isinstance(result, str)


# === CcCedictAdapter ===


class TestCcCedictAdapter:
    """Tests for CC-CEDICT dictionary adapter."""

    def test_implements_dictionary_port(self):
        """Adapter should implement the Dictionary port."""
        from langmine.adapters.cc_cedict import CcCedictAdapter
        adapter = CcCedictAdapter()
        assert isinstance(adapter, Dictionary)

    def test_lookup_common_word(self):
        """Should find a common Chinese word."""
        from langmine.adapters.cc_cedict import CcCedictAdapter
        adapter = CcCedictAdapter()
        result = adapter.lookup("你好")
        assert result is not None
        assert "definition_en" in result
        assert "definition_de" in result
        assert "pinyin" in result
        # "你好" should have pinyin
        assert "ni" in result["pinyin"].lower()

    def test_lookup_unknown_word_returns_none(self):
        """Should return None for non-existent words."""
        from langmine.adapters.cc_cedict import CcCedictAdapter
        adapter = CcCedictAdapter()
        result = adapter.lookup("xyzzy123")
        assert result is None

    def test_lookup_includes_german_when_available(self):
        """Should prefer German definition when present."""
        from langmine.adapters.cc_cedict import CcCedictAdapter
        adapter = CcCedictAdapter()
        # Many CC-CEDICT entries have German translations
        result = adapter.lookup("电脑")
        assert result is not None
        assert "definition_de" in result
        # At minimum, English fallback should exist
        assert len(result["definition_de"]) > 0 or len(result["definition_en"]) > 0

    def test_lookup_returns_consistent_structure(self):
        """Every lookup should return the same dict shape."""
        from langmine.adapters.cc_cedict import CcCedictAdapter
        adapter = CcCedictAdapter()
        for word in ["你好", "学习", "电脑", "爱"]:
            result = adapter.lookup(word)
            if result:
                assert set(result.keys()) == {"definition_en", "definition_de", "pinyin"}


# === JiebaFrequencyAdapter ===


class TestJiebaFrequencyAdapter:
    """Tests for frequency adapter using jieba's built-in dictionary."""

    def test_implements_frequency_port(self):
        """Adapter should implement the FrequencySource port."""
        from langmine.adapters.jieba_frequency import JiebaFrequencyAdapter
        adapter = JiebaFrequencyAdapter()
        assert isinstance(adapter, FrequencySource)

    def test_get_frequency_common_word(self):
        """Common words should have a frequency rank."""
        from langmine.adapters.jieba_frequency import JiebaFrequencyAdapter
        adapter = JiebaFrequencyAdapter()
        rank = adapter.get_frequency("的")
        assert rank is not None
        assert rank > 0

    def test_get_frequency_unknown_returns_none(self):
        """Unknown words return None."""
        from langmine.adapters.jieba_frequency import JiebaFrequencyAdapter
        adapter = JiebaFrequencyAdapter()
        rank = adapter.get_frequency("xyzzy123")
        assert rank is None

    def test_common_words_have_lower_ranks(self):
        """More common words should have lower frequency ranks."""
        from langmine.adapters.jieba_frequency import JiebaFrequencyAdapter
        adapter = JiebaFrequencyAdapter()
        rank_de = adapter.get_frequency("的")       # extremely common
        rank_diannao = adapter.get_frequency("电脑")  # moderately common
        if rank_de and rank_diannao:
            assert rank_de < rank_diannao, (
                f"的 (rank {rank_de}) should be more common than 电脑 (rank {rank_diannao})"
            )

    def test_frequency_tiers(self):
        """Tier logic should be accessible from domain models."""
        from langmine.domain.models import frequency_tier, frequency_badge
        assert frequency_tier(1) == "core"
        assert frequency_tier(2000) == "core"
        assert frequency_tier(2001) == "useful"
        assert frequency_badge(1) == "🔥"
        assert frequency_badge(6001) == "💎"
        assert frequency_badge(None) == ""
