"""Language extensions package.

Each sub-package (chinese/, spanish/, etc.) provides a LanguageProcessor
implementation plus language-specific adapters (dictionary, frequency).
Only language_factory.py is allowed to import from this package.
"""