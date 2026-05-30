"""Compatibility shim — wires default adapters behind language services.

This module imports domain services and injects real adapters.
Tests and domain code use the ports directly — this is just for convenience.

After M2, this module will be superseded by proper dependency injection.
"""

from langmine.domain.ports import LanguageProcessor
from langmine.languages.chinese import ChineseLanguageService


def get_processor(language_code: str) -> LanguageProcessor:
    """Get a LanguageProcessor with real adapters wired in.

    For tests and domain code, instantiate the language service directly
    with injected ports instead of using this convenience function.
    """
    from langmine.adapters.sqlite_persistence import SQLitePersistence

    # Import adapters lazily to avoid circular imports
    if language_code == "zh":
        # TODO: replace with real adapters in M2/M4
        # For now, this is a stub — use ChineseLanguageService(ports) directly
        raise NotImplementedError(
            "get_processor() with real adapters will be implemented in M2/M4. "
            "For now, use ChineseLanguageService(dict, translator, frequency) "
            "with injected ports."
        )
    else:
        raise ValueError(
            f"No processor for language '{language_code}'."
        )
