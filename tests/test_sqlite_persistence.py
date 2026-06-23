"""Tests for SQLitePersistence adapter."""

from langmine.adapters.sqlite_persistence import SQLitePersistence
from langmine.domain.models import Sentence, VocabWord


def test_get_sentences_by_words_caps_per_word():
    p = SQLitePersistence(":memory:")

    # 10 sentences for word "的"
    for i in range(10):
        p.save_sentences(
            [
                Sentence(
                    video_id=1,
                    start_ms=0,
                    end_ms=100,
                    text=f"的text{i}",
                    unknown_word="的",
                    status="new",
                )
            ]
        )

    # 3 sentences for word "我"
    for i in range(3):
        p.save_sentences(
            [
                Sentence(
                    video_id=1,
                    start_ms=0,
                    end_ms=100,
                    text=f"我text{i}",
                    unknown_word="我",
                    status="new",
                )
            ]
        )

    result = p.get_sentences_by_words(["的", "我", "吗"], max_per_word=5)

    assert len(result["的"]) == 5, f"Expected 5 for '的', got {len(result['的'])}"
    assert len(result["我"]) == 3, f"Expected 3 for '我', got {len(result['我'])}"
    assert len(result["吗"]) == 0, f"Expected 0 for '吗', got {len(result['吗'])}"


def test_get_sentences_by_words_empty_words():
    p = SQLitePersistence(":memory:")
    assert p.get_sentences_by_words([]) == {}


def test_get_sentences_by_words_returns_newest_first():
    p = SQLitePersistence(":memory:")

    sentences = [
        Sentence(
            video_id=1,
            start_ms=0,
            end_ms=100,
            text=f"你好text{i}",
            unknown_word="你好",
            status="new",
        )
        for i in range(3)
    ]
    p.save_sentences(sentences)

    result = p.get_sentences_by_words(["你好"], max_per_word=5)
    assert len(result["你好"]) == 3

    # Verify ordering: most recent first (id DESC)
    ids = [s.id for s in result["你好"]]
    assert ids == sorted(ids, reverse=True), (
        f"Expected descending order by id, got {ids}"
    )


def test_update_vocab_status_upserts_new_word():
    p = SQLitePersistence(":memory:")
    p.update_vocab_status("测试", "learning", "zh")
    word = p.get_vocab_word("测试")
    assert word is not None
    assert word.status == "learning"


def test_update_vocab_status_preserves_existing_fields():
    p = SQLitePersistence(":memory:")
    p.save_vocab_word(
        VocabWord(
            word_simplified="的",
            reading="de",
            definition_de="Partikel",
            hsk_level=1,
            frequency_rank=1,
            status="known",
            language_code="zh",
        )
    )
    p.update_vocab_status("的", "ignored", "zh")
    word = p.get_vocab_word("的")
    assert word.status == "ignored"
    assert word.reading == "de"
    assert word.definition_de == "Partikel"
    assert word.hsk_level == 1
    assert word.frequency_rank == 1
