"""Language processor factory — creates the right LanguageProcessor per config.

This is the ONLY module allowed to import from languages/.
Core code (domain/, pipeline.py, web/) uses the factory to get
a LanguageProcessor without knowing which language is configured.
"""

from langmine.domain.ports import LanguageProcessor
from langmine.config import Config


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
