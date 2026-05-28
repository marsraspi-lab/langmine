"""Tests for SubtlexChAdapter."""

import pytest

from langmine.adapters.subtlex_ch import SubtlexChAdapter


@pytest.fixture
def adapter():
    """Create SubtlexChAdapter from the real data file."""
    return SubtlexChAdapter()


def test_loads_all_entries(adapter):
    """The adapter should load ~99K entries from the SUBTLEX-CH corpus."""
    assert adapter.total_entries > 90000
    assert adapter.total_entries <= 100000


def test_rank_ordering(adapter):
    """More common words should have lower rank numbers."""
    的_rank = adapter.get_frequency("的")  # most common
    我_rank = adapter.get_frequency("我")  # second

    assert 的_rank is not None
    assert 我_rank is not None
    assert 的_rank < 我_rank  # 的 is more common than 我


def test_higher_rank_is_less_common(adapter):
    """A rare word should have a high rank, a common word a low rank."""
    common_rank = adapter.get_frequency("的")
    assert common_rank is not None
    assert common_rank <= 100  # 的 is in top 100


def test_unknown_word_returns_none(adapter):
    """Words not in the corpus return None."""
    assert adapter.get_frequency("thisisnotachineseword") is None


def test_tier_boundaries():
    """get_tier returns correct tier labels."""
    assert SubtlexChAdapter.get_tier(1) == "core"
    assert SubtlexChAdapter.get_tier(2000) == "core"
    assert SubtlexChAdapter.get_tier(2001) == "useful"
    assert SubtlexChAdapter.get_tier(6000) == "useful"
    assert SubtlexChAdapter.get_tier(6001) == "rare"


def test_badge():
    """get_badge returns correct emoji badges."""
    assert SubtlexChAdapter.get_badge(1) == "🔥"
    assert SubtlexChAdapter.get_badge(2000) == "🔥"
    assert SubtlexChAdapter.get_badge(2001) == "⭐"
    assert SubtlexChAdapter.get_badge(6000) == "⭐"
    assert SubtlexChAdapter.get_badge(6001) == "💎"
    assert SubtlexChAdapter.get_badge(None) == ""


def test_common_words_have_expected_ranks(adapter):
    """Spot-check: extremely common words should be in top ranks."""
    assert adapter.get_frequency("的") == 1  # THE most common word
    assert adapter.get_frequency("我") == 2
    assert adapter.get_frequency("你") == 3

    # All top-10 words should have rank <= 10
    top_words = ["的", "我", "你", "是", "了", "不", "在", "他", "我们"]
    for word in top_words:
        rank = adapter.get_frequency(word)
        assert rank is not None, f"{word} should be in SUBTLEX-CH"
        assert rank <= 10, f"{word} expected top-10, got rank {rank}"


def test_given_words_have_correct_tiers(adapter):
    """Verify a few known words get expected tiers."""
    assert adapter.get_frequency("的") is not None
    assert SubtlexChAdapter.get_tier(adapter.get_frequency("的")) == "core"

    # Some useful but not top-2000 word
    assert adapter.get_frequency("外行话") is not None
    # 外行话 has rank near the end
    tier = SubtlexChAdapter.get_tier(adapter.get_frequency("外行话"))
    assert tier == "rare"
