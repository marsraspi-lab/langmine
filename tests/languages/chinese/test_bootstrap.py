"""Tests for ChineseLanguageService.bootstrap_proficiency() — HSK bootstrapping."""

from langmine.domain.models import VocabWord
from langmine.domain.ports import Dictionary, FrequencySource, Translator
from langmine.languages.chinese.service import ChineseLanguageService


class FakeDictionary(Dictionary):
    def lookup(self, word: str) -> dict | None:
        return None


class FakeTranslator(Translator):
    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        return text


class FakeFrequency(FrequencySource):
    def get_frequency(self, word: str) -> int | None:
        return None

    def list_words(self, offset: int = 0, limit: int = 100) -> list[tuple[str, int]]:
        return []

    def count_words(self) -> int:
        return 0


class FakePersistence:
    """Minimal fake for bootstrap_proficiency tests."""

    def __init__(self):
        self._vocab: list[VocabWord] = []

    def get_vocab_word(self, word_simplified: str) -> VocabWord | None:
        for w in self._vocab:
            if w.word_simplified == word_simplified:
                return w
        return None

    def save_vocab_word(self, w: VocabWord) -> None:
        self._vocab.append(w)


def make_processor() -> ChineseLanguageService:
    return ChineseLanguageService(
        dictionary=FakeDictionary(),
        translator=FakeTranslator(),
        frequency=FakeFrequency(),
    )


def test_bootstrap_disabled_when_level_zero():
    """bootstrap_proficiency should do nothing when bootstrap_level is 0."""
    persistence = FakePersistence()
    processor = make_processor()

    processor.bootstrap_proficiency(
        persistence, settings={"bootstrap_level": 0}, language_code="zh"
    )

    assert len(persistence._vocab) == 0


def test_bootstrap_marks_hsk1_words_as_known():
    """HSK level 1 words should be saved as known when bootstrap_level is 1."""
    persistence = FakePersistence()
    processor = make_processor()

    processor.bootstrap_proficiency(
        persistence, settings={"bootstrap_level": 1}, language_code="zh"
    )

    # HSK 1 has ~150 words — all should be saved
    assert len(persistence._vocab) > 0
    for w in persistence._vocab:
        assert w.status == "known"
        assert w.hsk_level <= 1
        assert w.language_code == "zh"


def test_bootstrap_respects_level_boundary():
    """Only words up to max_level should be marked."""
    persistence = FakePersistence()
    processor = make_processor()

    processor.bootstrap_proficiency(
        persistence, settings={"bootstrap_level": 3}, language_code="zh"
    )

    for w in persistence._vocab:
        assert w.hsk_level <= 3
        # No HSK 4+ words
        assert not (w.hsk_level and w.hsk_level > 3)


def test_bootstrap_skips_existing_words():
    """Words already in vocab should not be overwritten."""
    persistence = FakePersistence()
    # Pre-populate with a known word set to "learning"
    persistence._vocab.append(
        VocabWord(
            word_simplified="我们",
            hsk_level=1,
            status="learning",  # user marked as learning, not known
            language_code="zh",
        )
    )
    processor = make_processor()

    processor.bootstrap_proficiency(
        persistence, settings={"bootstrap_level": 1}, language_code="zh"
    )

    # "我们" should still be "learning" (not overwritten)
    existing = persistence.get_vocab_word("我们")
    assert existing is not None
    assert existing.status == "learning"


def test_bootstrap_noop_for_unimplemented_language():
    """Default LanguageProcessor.bootstrap_proficiency is a no-op."""
    # Any processor that doesn't override bootstrap_proficiency should no-op
    persistence = FakePersistence()

    # The default implementation on LanguageProcessor is a no-op
    # (ChineseLanguageService overrides it, so we test the fallback here indirectly)
    # Non-Chinese processors wouldn't have the HSK data file anyway
    from langmine.domain.ports import LanguageProcessor

    class NoopProcessor(LanguageProcessor):
        def segment(self, text):
            return []

        def get_reading(self, text):
            return ""

        def lookup_word(self, word):
            return None

        def translate_sentence(self, text):
            return ""

        def get_frequency(self, word):
            return None

        def is_non_word(self, token):
            return False

        def is_proper_name(self, token, context=""):
            return False

        def find_known_synonyms(self, word, known):
            return []

        def get_annotation(self, text):
            return "[]"

    processor = NoopProcessor()
    processor.bootstrap_proficiency(
        persistence, settings={"bootstrap_level": 5}, language_code="es"
    )

    assert len(persistence._vocab) == 0
