"""Test Flask server for Playwright E2E tests.

Starts LangMine with FakePersistence and pre-populated data so
Playwright tests don't need real YouTube/ffmpeg/SQLite.
"""

import os
import sys

# Add project to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from langmine.config import Config
from langmine.domain.models import Sentence, Video, VocabWord
from langmine.domain.ports import (
    AudioProcessor,
    ImageSearch,
    LanguageProcessor,
    Persistence,
    SubtitleInfo,
    TranscriptChunk,
    TranscriptSource,
)
from langmine.web.app import create_app

# === Fake AnkiExporter for E2E tests ===


class FakeAnkiExporter:
    """Fake AnkiExporter that returns success without AnkiConnect."""

    def export(
        self,
        sentences,
        deck_name,
        note_type_name,
        card_css=None,
        card_front=None,
        card_back=None,
        force_update_model=False,
        card_type="basic",
    ):
        return {
            "note_ids": [1001],
            "added": len(sentences),
            "duplicates": 0,
            "errors": [],
        }


class FakeImageSearch(ImageSearch):
    """Fake image search returning hardcoded placeholder images."""

    def search(self, query, count=5):
        return [
            f"https://placehold.co/200x200/333/eee?text={query}+1",
            f"https://placehold.co/200x200/333/eee?text={query}+2",
            f"https://placehold.co/200x200/333/eee?text={query}+3",
        ][:count]


# === Fake ports (same as test_web_api.py) ===


class FakeLanguageProcessor(LanguageProcessor):
    def segment(self, text):
        return text.split()

    def get_reading(self, text):
        return " ".join(f"py:{t}" for t in text.split())

    def lookup_word(self, word):
        return {"definition_de": f"def:{word}", "definition_en": f"def:{word}"}

    def translate_sentence(self, text):
        return f"[DE] {text}"

    def get_frequency(self, word):
        ranks = {"一般": 1847, "效率": 3412, "爬山": 5000, "管理": 2100}
        return ranks.get(word)

    _FAKE_PARTICLES = {
        "的",
        "了",
        "吗",
        "吧",
        "呢",
        "啊",
        "哦",
        "嗯",
        "嘛",
        "啦",
        "呀",
        "呗",
        "咯",
        "哈",
        "哇",
        "哎",
        "唉",
        "哟",
        "着",
        "过",
        "地",
        "得",
    }
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

    def is_non_word(self, token):
        """Mirrors ChineseLanguageService.is_non_word to avoid test/prod skew."""
        import re

        return (
            token in self._FAKE_PARTICLES
            or token in self._FAKE_NUMERALS
            or bool(re.match(r"^\d+$", token))
        )

    def is_proper_name(self, token, context_sentence=""):
        return token in {"李世民", "刘备", "北京"}

    def find_known_synonyms(self, word, known_words):
        return []

    def get_annotation(self, text):
        return "[]"


class FakePersistence(Persistence):
    def __init__(self):
        self._videos = []
        self._sentences = []
        self._next_vid = 1
        self._next_sid = 1
        self._vocab: dict[str, VocabWord] = {}
        self._known_words = {"我们", "早上", "起床", "学习", "我", "爱", "你"}

    def save_video(self, video):
        if video.id is None:
            video.id = self._next_vid
            self._next_vid += 1
            self._videos.append(video)

    def get_video(self, yt_id):
        for v in self._videos:
            if v.youtube_id == yt_id:
                return v
        return None

    def list_videos(self, language_code=""):
        return self._videos

    def delete_video(self, video_id: int) -> bool:
        return False  # not found in fake

    def save_sentences(self, sentences):
        for s in sentences:
            if s.id is None:
                s.id = self._next_sid
                self._next_sid += 1
            self._sentences.append(s)

    def get_sentences_by_video(self, video_id, status=None, language_code=""):
        results = [s for s in self._sentences if s.video_id == video_id]
        if status:
            results = [s for s in results if s.status == status]
        return results

    def update_sentence(self, s):
        for i, existing in enumerate(self._sentences):
            if existing.id == s.id:
                self._sentences[i] = s
                break

    def get_known_words(self, language_code=""):
        return self._known_words | {
            w for w, v in self._vocab.items() if v.status in ("known", "ignored")
        }

    def get_vocab_stats(self, language_code=""):
        known = sum(1 for v in self._vocab.values() if v.status == "known")
        learning = sum(1 for v in self._vocab.values() if v.status == "learning")
        return {"known": known, "learning": learning, "total": len(self._vocab)}

    def mark_word_known(self, w):
        if w in self._vocab:
            self._vocab[w].status = "known"
        else:
            self._vocab[w] = VocabWord(word_simplified=w, status="known")

    def mark_word_learning(self, w):
        if w in self._vocab:
            self._vocab[w].status = "learning"
        else:
            self._vocab[w] = VocabWord(word_simplified=w, status="learning")

    def mark_word_ignored(self, word_simplified: str) -> None:
        if word_simplified in self._vocab:
            self._vocab[word_simplified].status = "ignored"
        else:
            from langmine.domain.models import VocabWord

            self._vocab[word_simplified] = VocabWord(
                word_simplified=word_simplified, status="ignored"
            )

    def save_vocab_word(self, w):
        self._vocab[w.word_simplified] = w

    def get_vocab_word(self, w):
        return self._vocab.get(w)

    def get_sentences_by_status(self, status, language_code=""):
        return [s for s in self._sentences if s.status == status]

    def list_vocab(
        self,
        page=1,
        per_page=200,
        status=None,
        search=None,
        sort="frequency",
        language_code="",
    ):
        words = list(self._vocab.values())
        if status:
            words = [w for w in words if w.status == status]
        if search:
            words = [
                w
                for w in words
                if search.lower() in w.word_simplified.lower()
                or search.lower() in (w.reading or "").lower()
            ]
        words.sort(key=lambda w: (w.frequency_rank is None, w.frequency_rank or 999999))
        total = len(words)
        start = (page - 1) * per_page
        return words[start : start + per_page], total

    def get_sentences_by_word(self, word):
        return [s for s in self._sentences if s.unknown_word == word or word in s.text]

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


class FakeTranscriptSource(TranscriptSource):
    def __init__(self, subtitles=None):
        self._subtitles = subtitles or {}

    def fetch(self, video_id, language=""):
        return [
            TranscriptChunk(text="我们", start_ms=0, duration_ms=500),
            TranscriptChunk(text="一般", start_ms=600, duration_ms=400),
            TranscriptChunk(text="早上", start_ms=1100, duration_ms=400),
            TranscriptChunk(text="七点", start_ms=1600, duration_ms=300),
            TranscriptChunk(text="起床", start_ms=2000, duration_ms=500),
        ]

    def list_subtitles(self, video_id):
        return self._subtitles.get(video_id, [])


class FakeAudioProcessor(AudioProcessor):
    def download(self, video_id, output_dir):
        return f"{output_dir}/{video_id}.mp3"

    def clip(self, audio_path, start_ms, end_ms, pad_before_ms, pad_after_ms, output_dir, sentence_id):
        return "/tmp/clip.mp3"

    def capture_frame(self, video_id, timestamp_ms, output_dir, sentence_id):
        return None  # no real screenshots in E2E tests


# === Create app ===

import struct
import tempfile
import zlib

# Create a valid 1×1 white PNG for the screenshot test fixture.
# Generated with Python stdlib only (no Pillow dependency).
_SCREENSHOT_PATH = os.path.join(tempfile.gettempdir(), "e2e_test_screenshot.png")


def _png_pack(png_tag, data):
    """Pack data into a PNG chunk."""
    chunk = png_tag + data
    return (
        struct.pack("!I", len(data))
        + chunk
        + struct.pack("!I", zlib.crc32(chunk) & 0xFFFFFFFF)
    )


def _make_1x1_png():
    """Return bytes for a valid 1×1 white PNG."""
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack("!IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    raw = b"\x00\xff\xff\xff"  # filter=0, R=255, G=255, B=255
    return (
        signature
        + _png_pack(b"IHDR", ihdr_data)
        + _png_pack(b"IDAT", zlib.compress(raw))
        + _png_pack(b"IEND", b"")
    )


with open(_SCREENSHOT_PATH, "wb") as f:
    f.write(_make_1x1_png())

persistence = FakePersistence()

# Pre-populate with a video and sentences
video = Video(youtube_id="dQw4w9WgXcQ", title="Test Video", channel="Test Channel")
persistence.save_video(video)

sentences = [
    # i+1 sentence with all fields filled (for edit + screenshot tests)
    Sentence(
        video_id=video.id,
        start_ms=1000,
        end_ms=3000,
        text="我们 一般 早上 起床",
        text_segmented="我们 / 一般 / 早上 / 起床",
        reading="wǒmen yībān zǎoshang qǐchuáng",
        annotation_json="[]",
        translation="Wir stehen normalerweise morgens auf",
        unknown_word="一般",
        unknown_word_rank=1847,
        audio_clip_path="",
        screenshot_path=_SCREENSHOT_PATH,
        screenshot_enabled=True,
        status="i1",
    ),
    # i+0 sentence
    Sentence(
        video_id=video.id,
        start_ms=4000,
        end_ms=7000,
        text="我 爱 学习",
        text_segmented="我 / 爱 / 学习",
        reading="wǒ ài xuéxí",
        annotation_json="[]",
        translation="Ich liebe es zu lernen",
        audio_clip_path="",
        status="i0",
    ),
    # Stashed sentence (i+2: 效率 + 管理 both unknown)
    Sentence(
        video_id=video.id,
        start_ms=8000,
        end_ms=12000,
        text="我们 需要 提高 效率 和 管理 水平",
        text_segmented="我们 / 需要 / 提高 / 效率 / 和 / 管理 / 水平",
        reading="wǒmen xūyào tígāo xiàolǜ hé guǎnlǐ shuǐpíng",
        annotation_json="[]",
        translation="Wir müssen Effizienz und Management verbessern",
        audio_clip_path="",
        status="stashed",
    ),
    # Kept sentence for M11 export tests
    Sentence(
        video_id=video.id,
        start_ms=13000,
        end_ms=16000,
        text="今天 天气 很 好",
        text_segmented="今天 / 天气 / 很 / 好",
        reading="jīntiān tiānqì hěn hǎo",
        annotation_json="[]",
        translation="Heute ist das Wetter sehr gut",
        unknown_word="天气",
        unknown_word_rank=2500,
        status="kept",
    ),
    # M20: proper name sentence for bracket display test
    Sentence(
        video_id=video.id,
        start_ms=17000,
        end_ms=20000,
        text="李世民 是 唐朝 皇帝",
        text_segmented="李世民 / 是 / 唐朝 / 皇帝",
        reading="lǐ shì mín shì táng cháo huáng dì",
        annotation_json="[]",
        translation="Li Shimin war ein Kaiser der Tang-Dynastie",
        unknown_word="皇帝",
        unknown_word_rank=3500,
        status="i1",
    ),
]
for s in sentences:
    persistence.save_sentences([s])

# M22: Add extra stashed sentences for pagination testing (>50 total)
for i in range(50):
    persistence.save_sentences(
        [
            Sentence(
                video_id=video.id,
                start_ms=20000 + i * 1000,
                end_ms=21000 + i * 1000,
                text=f"额外 句子 {i}",
                text_segmented=f"额外 / 句子 / {i}",
                status="stashed",
            )
        ]
    )

# Seed vocab words for M9 tests — word highlighting and vocab page
vocab_words = [
    VocabWord(
        word_simplified="一般",
        reading="yībān",
        definition_de="allgemein",
        hsk_level=3,
        frequency_rank=1847,
        status="learning",
    ),
    VocabWord(
        word_simplified="效率",
        reading="xiàolǜ",
        definition_de="Effizienz",
        hsk_level=5,
        frequency_rank=3412,
        status="learning",
    ),
    VocabWord(
        word_simplified="管理",
        reading="guǎnlǐ",
        definition_de="Verwaltung",
        hsk_level=4,
        frequency_rank=2100,
        status="learning",
    ),
    VocabWord(
        word_simplified="学习",
        reading="xuéxí",
        definition_de="lernen",
        hsk_level=1,
        frequency_rank=500,
        status="known",
    ),
    VocabWord(
        word_simplified="我们",
        reading="wǒmen",
        definition_de="wir",
        hsk_level=1,
        frequency_rank=100,
        status="known",
    ),
    VocabWord(
        word_simplified="早上",
        reading="zǎoshang",
        definition_de="Morgen",
        hsk_level=1,
        frequency_rank=800,
        status="known",
    ),
    VocabWord(
        word_simplified="起床",
        reading="qǐchuáng",
        definition_de="aufstehen",
        hsk_level=2,
        frequency_rank=1500,
        status="known",
    ),
    VocabWord(
        word_simplified="我",
        reading="wǒ",
        definition_de="ich",
        hsk_level=1,
        frequency_rank=10,
        status="known",
    ),
    VocabWord(
        word_simplified="爱",
        reading="ài",
        definition_de="lieben",
        hsk_level=1,
        frequency_rank=300,
        status="known",
    ),
]
for w in vocab_words:
    persistence.save_vocab_word(w)

# Subtitle seed data for E2E tests
# jNQXAC9IVRw = manual Chinese, dQw4w9WgXcQ = auto English, aAaAaAaAaAa = multi-lang
subtitles_map = {
    "jNQXAC9IVRw": [SubtitleInfo("zh-Hans", "Chinese (Simplified)", "manual")],
    "dQw4w9WgXcQ": [SubtitleInfo("en", "English", "auto")],
    "aAaAaAaAaAa": [
        SubtitleInfo("zh-Hans", "Chinese (Simplified)", "manual"),
        SubtitleInfo("en", "English", "manual"),
        SubtitleInfo("ja", "Japanese", "auto"),
    ],
}

# Create a temporary directory for config to avoid permission issues in tests
temp_config_dir = tempfile.mkdtemp(prefix="langmine_e2e_config_")

app = create_app(
    persistence=persistence,
    language_processor=FakeLanguageProcessor(),
    transcript_source=FakeTranscriptSource(subtitles=subtitles_map),
    audio_processor=FakeAudioProcessor(),
    anki_exporter=FakeAnkiExporter(),
    image_searcher=FakeImageSearch(),
    config=Config(),
    config_dir=temp_config_dir,
)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8099, debug=False)
