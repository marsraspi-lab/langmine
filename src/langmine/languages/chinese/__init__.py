"""Chinese language extension for LangMine.

Provides:
  - ChineseLanguageService (LanguageProcessor implementation)
  - CcCedictAdapter (Dictionary implementation)
  - SubtlexChAdapter (FrequencySource implementation)
  - JiebaFrequencyAdapter (fallback FrequencySource)
  - get_hsk_level (HSK proficiency utility)
"""

from langmine.languages.chinese.service import ChineseLanguageService
from langmine.languages.chinese.dictionary import CcCedictAdapter
from langmine.languages.chinese.frequency import SubtlexChAdapter
from langmine.languages.chinese.jieba_frequency import JiebaFrequencyAdapter
from langmine.languages.chinese.hsk_data import get_hsk_level

__all__ = [
    "ChineseLanguageService",
    "CcCedictAdapter",
    "SubtlexChAdapter",
    "JiebaFrequencyAdapter",
    "get_hsk_level",
]
