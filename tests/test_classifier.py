"""Tests for SentenceClassifier — the i+1 classification engine.

Tested against fake ports only. No YouTube, no SQLite, no network.
"""

import pytest

from langmine.domain.classifier import SentenceClassifier
from langmine.domain.ports import LanguageProcessor, Persistence, MergedSentence
from langmine.domain.models import Sentence, VocabWord


# === Fake Ports ===


class FakeLanguageProcessor(LanguageProcessor):
    """Returns predictable segmentation with configurable known/unknown words."""

    def __init__(self, known_words: set[str] | None = None):
        self._known_words = known_words or set()

    def segment(self, text: str) -> list[str]:
        # Simple space-based split for testing
        return text.split()

    def get_reading(self, text: str) -> str:
        return text

    def lookup_word(self, word: str) -> dict | None:
        return {"definition_de": f"def:{word}", "definition_en": f"def:{word}"}

    def translate_sentence(self, text: str) -> str:
        return f"[DE] {text}"

    def get_frequency(self, word: str) -> int | None:
        # Return mock frequency ranks
        ranks = {"一般": 1847, "效率": 3412, "斟酌": 8203, "爬山": 5000}
        return ranks.get(word)

    def is_non_word(self, token: str) -> bool:
        return token in {"的", "了", "吗", "123", "七点"}

    def is_proper_name(self, token): return False

    def find_known_synonyms(self, word, known_words): return []
    def get_annotation(self, text): return "[]"


class FakePersistence(Persistence):
    """In-memory persistence with known vocab."""

    def __init__(self, known_words: set[str] | None = None):
        self._known = known_words or set()
        self._ignored = set()
        self.videos_list: list = []
        self.sentences_list: list[Sentence] = []

    def get_known_words(self, language_code: str = "") -> set[str]:
        return self._known | self._ignored

    def save_video(self, video): self.videos_list.append(video)
    def get_video(self, yt_id): return None
    def list_videos(self, language_code: str = ""): return self.videos_list
    def video_exists(self, yt_id): return False
    def delete_video(self, video_id: int) -> bool:
        return False  # not found in fake
    def save_sentences(self, sentences): self.sentences_list.extend(sentences)
    def get_sentences_by_video(self, vid, status=None):
        return [s for s in self.sentences_list if s.video_id == vid]
    def get_stash_candidates(self, limit=20): return []
    def update_sentence(self, s): pass
    def get_sentences_by_status(self, status, language_code: str = ""): return []
    def reclassify_stashed(self, vid): return 0
    def save_vocab_word(self, w): pass
    def get_vocab_word(self, w): return None
    def mark_word_known(self, w): pass
    def mark_word_learning(self, w): pass
    def get_vocab_stats(self, language_code: str = ""): return {"known": 0, "learning": 0, "total": 0}
    def list_vocab(self, page=1, per_page=200, status=None, search=None, sort="frequency", language_code: str = ""):
        return [], 0
    def get_sentences_by_word(self, word):
        return [s for s in self.sentences_list
                if s.unknown_word == word or word in s.text]

    def mark_word_ignored(self, word_simplified: str) -> None:
        self._ignored.add(word_simplified)

    def log_event(
        self,
        entity_type: str,
        entity_id: int,
        action: str,
        old_value: str = "",
        new_value: str = "",
        language_code: str = "",
    ) -> None:
        pass


# === Tests ===


def make_sentences(*texts: str) -> list[MergedSentence]:
    """Helper: create MergedSentence objects from text strings."""
    return [
        MergedSentence(text=t, start_ms=i * 1000, end_ms=(i + 1) * 1000)
        for i, t in enumerate(texts)
    ]


class TestI1Classification:

    def test_i1_sentence_with_one_unknown(self):
        """Sentence with exactly one unknown word → i1."""
        processor = FakeLanguageProcessor()
        persistence = FakePersistence(known_words={"我们", "早上", "七点", "起床"})
        classifier = SentenceClassifier(processor, persistence)

        sentences = make_sentences("我们 一般 早上 七点 起床")
        results = classifier.classify(video_id=1, sentences=sentences)

        assert len(results) == 1
        assert results[0].status == "i1"
        assert results[0].unknown_word == "一般"

    def test_i0_sentence_all_known(self):
        """Sentence with all known words → i0."""
        processor = FakeLanguageProcessor()
        persistence = FakePersistence(known_words={"我", "爱", "学习"})
        classifier = SentenceClassifier(processor, persistence)

        sentences = make_sentences("我 爱 学习")
        results = classifier.classify(video_id=1, sentences=sentences)

        assert len(results) == 1
        assert results[0].status == "i0"
        assert results[0].unknown_word is None

    def test_stashed_sentence_multiple_unknown(self):
        """Sentence with 2+ unknown words → stashed."""
        processor = FakeLanguageProcessor()
        persistence = FakePersistence(known_words={"我"})  # only "我" is known
        classifier = SentenceClassifier(processor, persistence)

        sentences = make_sentences("我 一般 早上 七点 起床")  # 4 unknown
        results = classifier.classify(video_id=1, sentences=sentences)

        assert len(results) == 1
        assert results[0].status == "stashed"
        assert results[0].unknown_word is None

    def test_non_words_are_excluded_from_counting(self):
        """Particles and numbers should not affect i+1 count."""
        processor = FakeLanguageProcessor()
        persistence = FakePersistence(known_words={"我们", "早上", "起床"})
        classifier = SentenceClassifier(processor, persistence)

        # "的" and "了" are non-words → filtered out. Only "一般" is unknown → i1
        sentences = make_sentences("我们 的 一般 了 早上 起床")
        results = classifier.classify(video_id=1, sentences=sentences)

        assert len(results) == 1
        assert results[0].status == "i1"
        assert results[0].unknown_word == "一般"


class TestFrequencySorting:

    def test_i1_candidates_sorted_by_frequency(self):
        """i+1 candidates should be sorted by frequency rank (most common first)."""
        processor = FakeLanguageProcessor()
        # Only "我们" is known → each sentence must have exactly 1 other unknown
        persistence = FakePersistence(known_words={"我们", "学习"})
        classifier = SentenceClassifier(processor, persistence)

        sentences = make_sentences(
            "我们 一般 学习",   # unknowns: 一般(1847) only → i1
            "我们 效率 学习",   # unknowns: 效率(3412) only → i1
            "我们 斟酌 学习",   # unknowns: 斟酌(8203) only → i1
        )
        results = classifier.classify(video_id=1, sentences=sentences)

        # i+1 candidates sorted by frequency (ascending rank = more common first)
        i1 = [s for s in results if s.status == "i1"]
        assert len(i1) == 3
        assert i1[0].unknown_word == "一般"      # rank 1847
        assert i1[1].unknown_word == "效率"      # rank 3412
        assert i1[2].unknown_word == "斟酌"      # rank 8203

    def test_unknown_frequency_sorted_last(self):
        """Words with no frequency data should sort after known frequencies."""
        processor = FakeLanguageProcessor()
        persistence = FakePersistence(known_words={"我们", "学习"})
        classifier = SentenceClassifier(processor, persistence)

        sentences = make_sentences(
            "我们 爬山 学习",     # unknowns: 爬山(5000) only → i1
            "我们 一般 学习",     # unknowns: 一般(1847) only → i1
        )
        results = classifier.classify(video_id=1, sentences=sentences)

        i1 = [s for s in results if s.status == "i1"]
        assert len(i1) == 2
        assert i1[0].unknown_word == "一般"   # 1847 — more common
        assert i1[1].unknown_word == "爬山"   # 5000


class TestCap:

    def test_max_cards_cap(self):
        """Only max_cards i+1 sentences should be returned."""
        processor = FakeLanguageProcessor()
        persistence = FakePersistence(known_words={"我"})
        classifier = SentenceClassifier(processor, persistence)

        # Create 30 sentences, each with one unique unknown word
        texts = [f"我 word{i}" for i in range(30)]
        sentences = make_sentences(*texts)
        results = classifier.classify(video_id=1, sentences=sentences, max_cards=20)

        i1 = [s for s in results if s.status == "i1"]
        assert len(i1) == 20

    def test_stashed_not_capped(self):
        """Stashed sentences should not be limited by max_cards (they need full count)."""
        processor = FakeLanguageProcessor()
        persistence = FakePersistence(known_words=set())  # nothing known
        classifier = SentenceClassifier(processor, persistence)

        texts = [f"word{i} word{i}a word{i}b" for i in range(25)]
        sentences = make_sentences(*texts)
        results = classifier.classify(video_id=1, sentences=sentences, max_cards=20)

        stashed = [s for s in results if s.status == "stashed"]
        assert len(stashed) == 25  # all stashed, no cap


class TestStatusSummary:

    def test_classify_returns_summary(self):
        """classify() should return all sentences with correct status counts."""
        processor = FakeLanguageProcessor()
        persistence = FakePersistence(known_words={"我", "爱", "你"})
        classifier = SentenceClassifier(processor, persistence)

        sentences = make_sentences(
            "我 爱 学习",          # "学习" unknown → i1
            "我 爱 你",            # all known → i0
            "今天 天气 很好 啊",    # 3 unknown (今天,天气,很好) + 啊 non-word → stashed
        )
        results = classifier.classify(video_id=1, sentences=sentences)

        i1_count = sum(1 for s in results if s.status == "i1")
        i0_count = sum(1 for s in results if s.status == "i0")
        stashed_count = sum(1 for s in results if s.status == "stashed")

        assert i1_count == 1
        assert i0_count == 1
        assert stashed_count == 1
        assert i1_count + i0_count + stashed_count == 3
