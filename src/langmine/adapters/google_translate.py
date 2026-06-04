"""Google Translate adapter using deep-translator.

Implements the Translator port.
"""

import logging

from langmine.domain.ports import Translator

logger = logging.getLogger(__name__)


class GoogleTranslateAdapter(Translator):
    """Translate text using Google Translate (free, no API key)."""

    def translate(
        self, text: str, source_lang: str = "zh", target_lang: str = "de"
    ) -> str:
        """Translate text from source_lang to target_lang.

        Args:
            text: The text to translate.
            source_lang: Source language code (default: 'zh').
            target_lang: Target language code (default: 'de').

        Returns:
            Translated string, or empty string on failure.
        """
        if not text.strip():
            return ""

        try:
            from deep_translator import GoogleTranslator

            # deep-translator uses 'zh-CN' not 'zh'
            src = "zh-CN" if source_lang == "zh" else source_lang
            result = GoogleTranslator(source=src, target=target_lang).translate(text)
            return result if result else ""
        except Exception as e:
            logger.warning("Google Translate failed for text %r: %s", text[:80], e)
            return ""
