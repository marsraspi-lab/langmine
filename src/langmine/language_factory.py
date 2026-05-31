"""Language processor factory — creates the right LanguageProcessor per config.

This is the ONLY module allowed to import from languages/.
Core code (domain/, pipeline.py, web/) uses the factory to get
a LanguageProcessor without knowing which language is configured.
"""

from langmine.domain.ports import LanguageProcessor
from langmine.config import Config


# Language metadata for UI — code + display name for each available language.
# Extend this when adding a new language extension.
LANGUAGES = [
    {"code": "zh", "name": "Chinese"},
    # {"code": "es", "name": "Spanish"},  # uncomment when implemented
    # {"code": "ko", "name": "Korean"},
    # {"code": "ru", "name": "Russian"},
]


def get_available_languages() -> list[dict]:
    """Return list of available languages: [{code, name}, ...].

    Only returns languages that successfully load (no NotImplementedError).
    """
    available = []
    for lang in LANGUAGES:
        code = lang["code"]
        try:
            _try_load_processor(code)
            available.append(lang)
        except NotImplementedError:
            continue  # skip languages not yet implemented
        except Exception:
            available.append(lang)  # let errors surface at call time
    return available


def _try_load_processor(lang_code: str) -> None:
    """Try to instantiate a processor for lang_code. Raises if not possible."""
    from langmine.adapters.google_translate import GoogleTranslateAdapter
    translator = GoogleTranslateAdapter()

    match lang_code:
        case "zh":
            from langmine.languages.chinese import (
                ChineseLanguageService,
                CcCedictAdapter,
                SubtlexChAdapter,
            )
            ChineseLanguageService(
                CcCedictAdapter(), translator, SubtlexChAdapter()
            )
        case _:
            raise NotImplementedError(
                f"Language '{lang_code}' not yet implemented."
            )


def create_language_processor(config: Config) -> LanguageProcessor:
    """Create a LanguageProcessor for the configured source language.

    Each language extension provides its own service + adapters.
    """
    from langmine.adapters.google_translate import GoogleTranslateAdapter

    translator = GoogleTranslateAdapter()

    match config.source_language:
        case "zh":
            from langmine.languages.chinese import (
                ChineseLanguageService,
                CcCedictAdapter,
                SubtlexChAdapter,
            )
            return ChineseLanguageService(
                CcCedictAdapter(),
                translator,
                SubtlexChAdapter(),
            )

        case "es":
            raise NotImplementedError(
                "Spanish language extension not yet implemented. "
                "Create languages/spanish/ with SpanishLanguageService."
            )

        case "ko":
            raise NotImplementedError(
                "Korean language extension not yet implemented. "
                "Create languages/korean/ with KoreanLanguageService."
            )

        case "ru":
            raise NotImplementedError(
                "Russian language extension not yet implemented. "
                "Create languages/russian/ with RussianLanguageService."
            )

        case _:
            raise ValueError(
                f"Unsupported source language: {config.source_language}. "
                "Add a language extension under languages/<lang>/."
            )


def get_proficiency_level(word: str) -> int | None:
    """Return a proficiency level for a word (e.g. HSK 1-6), or None.

    Delegates to the proficiency framework of the configured language.
    Currently only Chinese (HSK) is supported. Returns None for other
    languages or when no proficiency data matches the word.
    """
    from langmine.config import load_config

    config = load_config()

    if config.source_language == "zh":
        from langmine.languages.chinese.hsk_data import get_hsk_level
        return get_hsk_level(word)

    # Other languages don't have proficiency frameworks yet
    return None


def get_anki_templates(lang_code: str) -> dict:
    """Load Anki card templates for a language from its anki/ directory.

    Returns dict with: basic_front, basic_back, basic_css,
    cloze_front, cloze_back, cloze_css.
    Falls back to empty strings for unimplemented languages.
    """
    match lang_code:
        case "zh":
            from langmine.languages.chinese import get_anki_templates as _zh_templates
            return _zh_templates()
        case _:
            return {}


def get_language_manifest(lang_code: str) -> dict:
    """Return the language manifest dict with deck_name, note_type, etc.

    Returns empty dict for unimplemented languages.
    """
    match lang_code:
        case "zh":
            from langmine.languages.chinese import MANIFEST
            return MANIFEST
        case _:
            return {}


def get_transcript_languages(lang_code: str) -> list[str]:
    """Return preferred YouTube transcript language codes for a language.

    Returns empty list for unimplemented languages (library default behavior).
    """
    match lang_code:
        case "zh":
            from langmine.languages.chinese import TRANSCRIPT_LANGUAGES
            return TRANSCRIPT_LANGUAGES
        case _:
            return []
