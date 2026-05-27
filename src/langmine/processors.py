"""Language processor plugin interface for LangMine.

Each target language implements the LanguageProcessor abstract base class.
"""

from abc import ABC, abstractmethod


class LanguageProcessor(ABC):
    """Abstract base for language-specific NLP processing.

    Each target language (Chinese, Spanish, Korean, Russian, etc.)
    implements this interface. The registry maps language codes to
    processor classes.
    """

    @abstractmethod
    def segment(self, text: str) -> list[str]:
        """Segment text into words/tokens."""

    @abstractmethod
    def get_reading(self, text: str) -> str:
        """Phonetic reading: pinyin for zh, IPA for es, etc."""

    @abstractmethod
    def lookup_word(self, word: str) -> dict | None:
        """Dictionary lookup. Returns definition dict with keys
        'definition_de' and 'definition_en'."""

    @abstractmethod
    def translate_sentence(self, text: str) -> str:
        """Sentence-level MT. Returns German translation."""

    @abstractmethod
    def get_frequency(self, word: str) -> int | None:
        """Frequency rank (lower = more common). None if unknown."""

    @abstractmethod
    def is_non_word(self, token: str) -> bool:
        """True if this token should be excluded from i+1 counting
        (particles, numbers, names, etc.)."""

    @abstractmethod
    def find_known_synonyms(
        self, word: str, known_words: set[str]
    ) -> list[str]:
        """Return any known synonyms of `word`."""


class ChineseProcessor(LanguageProcessor):
    """Chinese language processor using jieba, pypinyin, CC-CEDICT.

    Full implementation in M2. This is a stub for M0.
    """

    def segment(self, text: str) -> list[str]:
        return list(text)  # stub: character-level for now

    def get_reading(self, text: str) -> str:
        return text  # stub

    def lookup_word(self, word: str) -> dict | None:
        return None  # stub

    def translate_sentence(self, text: str) -> str:
        return ""  # stub

    def get_frequency(self, word: str) -> int | None:
        return None  # stub

    def is_non_word(self, token: str) -> bool:
        return False  # stub

    def find_known_synonyms(
        self, word: str, known_words: set[str]
    ) -> list[str]:
        return []  # stub


# Registry of language code → processor class
_PROCESSOR_REGISTRY: dict[str, type[LanguageProcessor]] = {
    "zh": ChineseProcessor,
}


def get_processor(language_code: str) -> LanguageProcessor:
    """Get a processor instance for the given language code."""
    processor_cls = _PROCESSOR_REGISTRY.get(language_code)
    if processor_cls is None:
        raise ValueError(
            f"No processor registered for language '{language_code}'. "
            f"Available: {list(_PROCESSOR_REGISTRY.keys())}"
        )
    return processor_cls()
