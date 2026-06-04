"""Language processor factory — creates the right LanguageProcessor per config.

This is the ONLY module allowed to import from languages/.
Core code (domain/, pipeline.py, web/) uses the factory to get
a LanguageProcessor without knowing which language is configured.

All port implementations (Translator, Dictionary, FrequencySource) are
resolved from config — no adapter is hardcoded.  Callers can also inject
ports directly for testing.

Language Registry (Open/Closed):
    Adding a language no longer requires editing this file.  Create a
    package under languages/<code>/ with the standard exports and call
    register_language() in its __init__.py.  The factory auto-discovers
    registered languages via pkgutil.iter_modules().
"""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Callable

from langmine.config import Config
from langmine.domain.ports import (
    Dictionary,
    FrequencySource,
    LanguageProcessor,
    Translator,
)

# === Language Registry ===

_LANGUAGE_REGISTRY: dict[str, dict] = {}


def register_language(
    code: str,
    *,
    name: str,
    service_class: type[LanguageProcessor],
    dictionary_class: type[Dictionary],
    frequency_class: type[FrequencySource],
    transcript_languages: list[str],
    manifest: dict | None = None,
    get_anki_templates: Callable[[], dict] | None = None,
    get_proficiency_level: Callable[[str], int | None] | None = None,
) -> None:
    """Register a language extension.

    Called from each language package's __init__.py at import time.
    All kwargs are keyword-only to keep the registry schema explicit.

    Args:
        code: ISO 639-1 language code (e.g. 'zh', 'es').
        name: Display name (e.g. 'Chinese', 'Spanish').
        service_class: LanguageProcessor subclass for this language.
        dictionary_class: Dictionary adapter class (no-arg constructible).
        frequency_class: FrequencySource adapter class (no-arg constructible).
        transcript_languages: YouTube subtitle codes in preference order.
        manifest: Anki/UI metadata dict (deck_name, note_type, etc.).
        get_anki_templates: Callable returning card template dict.
        get_proficiency_level: Proficiency lookup (e.g. HSK level), or None.
    """
    _LANGUAGE_REGISTRY[code] = {
        "name": name,
        "service_class": service_class,
        "dictionary_class": dictionary_class,
        "frequency_class": frequency_class,
        "transcript_languages": transcript_languages,
        "manifest": manifest or {},
        "get_anki_templates": get_anki_templates or (lambda: {}),
        "get_proficiency_level": get_proficiency_level,
    }


def _ensure_loaded(lang_code: str) -> None:
    """Ensure a language is registered, running discovery if needed.

    No-op if already registered.  Calls _discover_languages() to import
    all language packages (by directory name), which triggers each
    package's register_language() call and populates the code→entry mapping.
    Raises ValueError for unknown codes.
    """
    if lang_code in _LANGUAGE_REGISTRY:
        return

    # Discovery imports packages by directory name (e.g. "chinese"),
    # and each package's register_language() maps its logical code
    # (e.g. "zh") to its entry.
    _discover_languages()

    if lang_code not in _LANGUAGE_REGISTRY:
        raise ValueError(
            f"Unsupported source language: {lang_code}. "
            f"No registered language package found for this code."
        )


def _discover_languages() -> None:
    """Scan the languages/ directory and import all language packages.

    Imports each package by its directory name (e.g. "chinese").
    Each package's __init__.py calls register_language() at import time,
    which maps its logical code (e.g. "zh") to its entry in the registry.
    Broken packages (ImportError, etc.) are silently skipped.
    """
    import langmine.languages

    for _, name, _ in pkgutil.iter_modules(langmine.languages.__path__):
        if name in _LANGUAGE_REGISTRY:
            continue
        try:
            importlib.import_module(f"langmine.languages.{name}")
        except Exception:
            # Skip packages that fail to load (missing deps, syntax errors, etc.)
            pass


# === Public API ===


def get_available_languages() -> list[dict]:
    """Return list of available languages: [{code, name}, ...].

    Auto-discovers language packages under languages/ and returns
    every successfully registered language.
    """
    _discover_languages()
    return [
        {"code": code, "name": entry["name"]}
        for code, entry in _LANGUAGE_REGISTRY.items()
    ]


def create_language_processor(
    config: Config,
    translator: Translator,
    dictionary: Dictionary,
    frequency: FrequencySource,
) -> LanguageProcessor:
    """Create a LanguageProcessor for the configured source language.

    All ports are injected by the caller — no adapter is hardcoded.
    Wire real adapters in app.py; pass fakes for testing.

    Args:
        config: LangMine configuration.
        translator: Translator port implementation.
        dictionary: Dictionary port implementation.
        frequency: FrequencySource port implementation.
    """
    _ensure_loaded(config.source_language)
    service_class = _LANGUAGE_REGISTRY[config.source_language]["service_class"]
    return service_class(dictionary, translator, frequency)


def get_proficiency_level(word: str, language_code: str = "") -> int | None:
    """Return a proficiency level for a word (e.g. HSK 1-6), or None.

    Delegates to the proficiency framework registered for the language.
    Returns None when no proficiency framework is registered or when
    the word is not found in the framework.
    """
    if not language_code:
        return None

    _ensure_loaded(language_code)
    fn = _LANGUAGE_REGISTRY[language_code].get("get_proficiency_level")
    if fn is None:
        return None
    return fn(word)


def get_anki_templates(lang_code: str) -> dict:
    """Load Anki card templates for a language from its anki/ directory.

    Returns dict with: basic_front, basic_back, basic_css,
    cloze_front, cloze_back, cloze_css.
    Falls back to empty dict for languages without templates.
    """
    if not lang_code:
        return {}

    _ensure_loaded(lang_code)
    return _LANGUAGE_REGISTRY[lang_code]["get_anki_templates"]()


def get_language_manifest(lang_code: str) -> dict:
    """Return the language manifest dict with deck_name, note_type, etc.

    Returns empty dict for languages without a manifest.
    """
    if not lang_code:
        return {}

    _ensure_loaded(lang_code)
    return _LANGUAGE_REGISTRY[lang_code]["manifest"]


def get_transcript_languages(lang_code: str) -> list[str]:
    """Return preferred YouTube transcript language codes for a language.

    Returns empty list for languages without transcript configuration.
    """
    if not lang_code:
        return []

    _ensure_loaded(lang_code)
    return _LANGUAGE_REGISTRY[lang_code]["transcript_languages"]


def create_language_adapters(config: Config) -> tuple[Dictionary, FrequencySource]:
    """Create language-specific Dictionary and FrequencySource adapters.

    Called by app.py during wiring — the factory remains the single
    module allowed to import from languages/ (via lazy importlib loading).

    Returns:
        (dictionary, frequency) tuple for the configured source language.
    """
    _ensure_loaded(config.source_language)
    entry = _LANGUAGE_REGISTRY[config.source_language]
    return entry["dictionary_class"](), entry["frequency_class"]()
