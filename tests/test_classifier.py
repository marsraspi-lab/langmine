"""Tests for SentenceClassifier — the i+1 classification engine.

Tested against fake ports only. No YouTube, no SQLite, no network.
"""

from langmine.domain.classifier import SentenceClassifier
from langmine.domain.models import Sentence, VocabWord
from langmine.domain.ports import LanguageProcessor, MergedSentence, Persistence

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

    _FAKE_PARTICLES = {"的", "了", "吗", "吧", "呢", "啊"}
    _FAKE_NUMERALS = {
        "零",
        "一",
        "二",
        "三",
        "四",
        "五",
        "六",
        "七",
        "八",
        "九",
        "十",
        "百",
        "千",
        "万",
        "亿",
        "两",
    }

    def is_non_word(self, token: str) -> bool:
        """Mirrors ChineseLanguageService.is_non_word."""
        import re

        return (
            token in self._FAKE_PARTICLES
            or token in self._FAKE_NUMERALS
            or bool(re.match(r"^\d+$", token))
        )

    def is_proper_name(self, token, context_sentence=""):
        return False

    def find_known_synonyms(self, word, known_words):
        return []

    def get_annotation(self, text):
        return "[]"


class FakePersistence(Persistence):
    """In-memory persistence with known vocab."""

    def __init__(self, known_words: set[str] | None = None):
        self._known = known_words or set()
        self._ignored = set()
        self.videos_list: list = []
        self.sentences_list: list[Sentence] = []

    def get_known_words(self, language_code: str = "") -> set[str]:
        return self._known | self._ignored

    def save_video(self, video):
        self.videos_list.append(video)

    def get_video(self, yt_id):
        return None

    def list_videos(self, language_code: str = ""):
        return self.videos_list

    def delete_video(self, video_id: int) -> bool:
        return False  # not found in fake

    def save_sentences(self, sentences):
        self.sentences_list.extend(sentences)

    def get_sentences_by_video(self, vid, status=None):
        return [s for s in self.sentences_list if s.video_id == vid]

    def update_sentence(self, s):
        pass

    def get_sentences_by_status(self, status, language_code: str = ""):
        return []

    def save_vocab_word(self, w):
        pass

    def get_vocab_word(self, w):
        return None

    def mark_word_known(self, w):
        pass

    def mark_word_learning(self, w):
        pass

    def get_vocab_stats(self, language_code: str = ""):
        return {"known": 0, "learning": 0, "ignored": 0, "proper_name": 0, "total": 0}

    def get_vocab_statuses(self, words, language_code=""):
        return {}

    def get_words_by_status(self, status, language_code=""):
        return set()

    def get_classified_words(self, language_code=""):
        return set()

    def list_vocab(
        self,
        page=1,
        per_page=200,
        status=None,
        search=None,
        sort="frequency",
        language_code: str = "",
    ):
        return [], 0

    def get_sentences_by_word(self, word):
        return [
            s for s in self.sentences_list if s.unknown_word == word or word in s.text
        ]

    def get_sentences_by_words(self, words, max_per_word=5):
        result = {w: [] for w in words}
        for s in self.sentences_list:
            if s.unknown_word in result and len(result[s.unknown_word]) < max_per_word:
                result[s.unknown_word].append(s)
        return result

    def mark_word_ignored(self, word_simplified: str) -> None:
        self._ignored.add(word_simplified)

    def update_vocab_status(self, word_simplified, status, language_code=""):
        pass

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
            "我们 一般 学习",  # unknowns: 一般(1847) only → i1
            "我们 效率 学习",  # unknowns: 效率(3412) only → i1
            "我们 斟酌 学习",  # unknowns: 斟酌(8203) only → i1
        )
        results = classifier.classify(video_id=1, sentences=sentences)

        # i+1 candidates sorted by frequency (ascending rank = more common first)
        i1 = [s for s in results if s.status == "i1"]
        assert len(i1) == 3
        assert i1[0].unknown_word == "一般"  # rank 1847
        assert i1[1].unknown_word == "效率"  # rank 3412
        assert i1[2].unknown_word == "斟酌"  # rank 8203

    def test_unknown_frequency_sorted_last(self):
        """Words with no frequency data should sort after known frequencies."""
        processor = FakeLanguageProcessor()
        persistence = FakePersistence(known_words={"我们", "学习"})
        classifier = SentenceClassifier(processor, persistence)

        sentences = make_sentences(
            "我们 爬山 学习",  # unknowns: 爬山(5000) only → i1
            "我们 一般 学习",  # unknowns: 一般(1847) only → i1
        )
        results = classifier.classify(video_id=1, sentences=sentences)

        i1 = [s for s in results if s.status == "i1"]
        assert len(i1) == 2
        assert i1[0].unknown_word == "一般"  # 1847 — more common
        assert i1[1].unknown_word == "爬山"  # 5000


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
            "我 爱 学习",  # "学习" unknown → i1
            "我 爱 你",  # all known → i0
            "今天 天气 很好 啊",  # 3 unknown (今天,天气,很好) + 啊 non-word → stashed
        )
        results = classifier.classify(video_id=1, sentences=sentences)

        i1_count = sum(1 for s in results if s.status == "i1")
        i0_count = sum(1 for s in results if s.status == "i0")
        stashed_count = sum(1 for s in results if s.status == "stashed")

        assert i1_count == 1
        assert i0_count == 1
        assert stashed_count == 1
        assert i1_count + i0_count + stashed_count == 3


# === reclassify_all (M22) ===


class FakePersistenceWithSentences(Persistence):
    """Stores sentences and vocab for reclassify_all tests."""

    def __init__(self, known_words: set[str] | None = None):
        self._known = known_words or set()
        self._ignored = set()
        self._vocab: list[VocabWord] = []
        self._sentences: list[Sentence] = []

    def get_known_words(self, language_code: str = "") -> set[str]:
        return (
            self._known
            | self._ignored
            | {
                w.word_simplified
                for w in self._vocab
                if w.status in ("known", "ignored")
            }
        )

    def get_sentences_by_video(
        self, video_id: int, status=None, language_code: str = ""
    ):
        results = [s for s in self._sentences if s.video_id == video_id]
        if status:
            results = [s for s in results if s.status == status]
        return results

    def update_sentence(self, s: Sentence) -> None:
        for i, existing in enumerate(self._sentences):
            if existing.id == s.id:
                self._sentences[i] = s
                return

    # Stubs for abstract methods
    def save_video(self, v):
        pass

    def get_video(self, yt_id):
        return None

    def list_videos(self, language_code: str = ""):
        return []

    def delete_video(self, vid):
        return False

    def save_sentences(self, ss):
        pass

    def get_sentences_by_status(self, status, language_code: str = ""):
        return []

    def get_sentences_by_words(self, words, max_per_word=5):
        result = {w: [] for w in words}
        for s in self._sentences:
            if s.unknown_word in result and len(result[s.unknown_word]) < max_per_word:
                result[s.unknown_word].append(s)
        return result

    def save_vocab_word(self, w):
        pass

    def get_vocab_word(self, w):
        return None

    def mark_word_known(self, w):
        pass

    def mark_word_learning(self, w):
        pass

    def mark_word_ignored(self, w):
        pass

    def update_vocab_status(self, word_simplified, status, language_code=""):
        pass

    def get_vocab_stats(self, language_code: str = ""):
        known = sum(1 for w in self._vocab if w.status == "known")
        learning = sum(1 for w in self._vocab if w.status == "learning")
        ignored = sum(1 for w in self._vocab if w.status == "ignored")
        proper_name = sum(1 for w in self._vocab if w.status == "proper-name")
        return {
            "known": known,
            "learning": learning,
            "ignored": ignored,
            "proper_name": proper_name,
            "total": len(self._vocab),
        }

    def get_vocab_statuses(self, words, language_code=""):
        result = {}
        for w in words:
            vw = self.get_vocab_word(w)
            if vw:
                result[w] = vw.status
        return result

    def get_words_by_status(self, status, language_code=""):
        return {
            w.word_simplified
            for w in self._vocab
            if w.status == status
            and (not language_code or w.language_code == language_code)
        }

    def get_classified_words(self, language_code=""):
        return {
            w.word_simplified
            for w in self._vocab
            if w.status in ("known", "learning", "ignored", "proper-name")
            and (not language_code or w.language_code == language_code)
        }

    def list_vocab(
        self,
        page=1,
        per_page=200,
        status=None,
        search=None,
        sort="frequency",
        language_code: str = "",
    ):
        return [], 0

    def get_sentences_by_word(self, w):
        return []

    def log_event(self, **kw):
        pass


def _make_sentence(
    video_id: int,
    text_segmented: str,
    status: str = "stashed",
    unknown_word: str = "",
    unknown_word_rank: int | None = None,
) -> Sentence:
    """Helper: create a Sentence for reclassify_all tests."""
    return Sentence(
        id=hash(text_segmented) % 10000,
        video_id=video_id,
        start_ms=0,
        end_ms=1000,
        text=text_segmented.replace(" / ", ""),
        text_segmented=text_segmented,
        status=status,
        unknown_word=unknown_word,
        unknown_word_rank=unknown_word_rank,
    )


def test_reclassify_all_promotes_stashed_to_i1():
    """A stashed sentence with 2+ unknowns should promote to i1 when words are learned."""
    processor = FakeLanguageProcessor()
    persistence = FakePersistenceWithSentences(known_words={"我", "爱", "天气"})

    # "我" known, "爱" known, "天气" known → only unknown is "很好"
    s1 = _make_sentence(1, "我 / 爱 / 天气 / 很好", status="stashed")
    # "我" known, "中文" unknown → one unknown → should be i1
    s2 = _make_sentence(1, "我 / 学习 / 中文", status="stashed")
    persistence._sentences = [s1, s2]

    classifier = SentenceClassifier(processor, persistence)
    results = classifier.reclassify_all(1)

    # s1: 我(known), 爱(known), 天气(known), 很好(unknown) → 1 unknown → i1
    # s2: 我(known), 学习(unknown), 中文(unknown) → 2 unknowns → stashed
    assert results[0].status == "i1"  # best i1 first (only i1)
    assert results[1].status == "stashed"
    assert len(results) == 2


def test_reclassify_all_demotes_i1_to_i0():
    """An i1 sentence should demote to i0 if the unknown word is now known."""
    persistence = FakePersistenceWithSentences(known_words={"我们", "学习"})
    processor = FakeLanguageProcessor()

    # All words are now known
    s = _make_sentence(1, "我们 / 学习", status="i1", unknown_word="学习")
    persistence._sentences = [s]

    classifier = SentenceClassifier(processor, persistence)
    results = classifier.reclassify_all(1)

    assert results[0].status == "i0"


def test_reclassify_all_sorts_i1_by_frequency():
    """i1 candidates should be sorted by frequency rank (ascending)."""
    persistence = FakePersistenceWithSentences(known_words={"我"})
    processor = FakeLanguageProcessor()

    # "我" known → exactly 1 unknown each → both promoted to i1
    s1 = _make_sentence(1, "我 / 斟酌", status="stashed")
    s2 = _make_sentence(1, "我 / 一般", status="stashed")
    persistence._sentences = [s1, s2]

    classifier = SentenceClassifier(processor, persistence)
    results = classifier.reclassify_all(1)

    # "一般"(rank=1847) before "斟酌"(rank=8203)
    assert results[0].unknown_word == "一般"
    assert results[1].unknown_word == "斟酌"


def test_reclassify_all_sort_order():
    """Sort order: i1 candidates first, then i0, then stashed."""
    persistence = FakePersistenceWithSentences(known_words={"我"})
    processor = FakeLanguageProcessor()

    s_stashed = _make_sentence(
        1, "罕见 / 词语 / 很多", status="stashed"
    )  # 3 unknowns → stashed
    s_i0 = _make_sentence(1, "我", status="i0")  # all known → i0
    s_i1 = _make_sentence(
        1, "我 / 一个 / 猫", status="stashed"
    )  # "我" known, "一个" unknown, "猫" unknown → 2 unknowns → stashed

    persistence._sentences = [s_stashed, s_i0, s_i1]

    classifier = SentenceClassifier(processor, persistence)
    results = classifier.reclassify_all(1)

    # Only s_i0 is i0 (all known), rest stay stashed
    # Sort: i0 before stashed
    assert results[0].status == "i0"
    assert results[1].status == "stashed"
    assert results[2].status == "stashed"


class SpyLanguageProcessor(FakeLanguageProcessor):
    """LanguageProcessor that records translate_sentence calls."""

    def __init__(self):
        super().__init__()
        self.translate_calls: list[str] = []

    def translate_sentence(self, text: str) -> str:
        self.translate_calls.append(text)
        return f"[MT] {text}"


class TestEnrichSkipsMT:
    """enrich() should skip MT when translation is already set
    (e.g., from subtitle alignment)."""

    def test_enrich_skips_mt_when_translation_present(self):
        processor = SpyLanguageProcessor()
        persistence = FakePersistence()
        classifier = SentenceClassifier(processor, persistence)

        sentence = Sentence(
            text="你好",
            text_segmented="你好",
            video_id=1,
            start_ms=0,
            end_ms=1000,
            translation="Hallo",
        )
        classifier.enrich([sentence])

        # Translation was already "Hallo" — should not have called MT
        assert sentence.translation == "Hallo"
        assert len(processor.translate_calls) == 0

    def test_enrich_calls_mt_when_translation_empty(self):
        processor = SpyLanguageProcessor()
        persistence = FakePersistence()
        classifier = SentenceClassifier(processor, persistence)

        sentence = Sentence(
            text="你好",
            text_segmented="你好",
            video_id=1,
            start_ms=0,
            end_ms=1000,
            translation="",
        )
        classifier.enrich([sentence])

        # Translation was empty — should have called MT
        assert sentence.translation == "[MT] 你好"
        assert len(processor.translate_calls) == 1
