"""Test Flask server for Playwright E2E tests.

Starts LangMine with FakePersistence and pre-populated data so
Playwright tests don't need real YouTube/ffmpeg/SQLite.
"""

import json
import os
import sys
import threading

# Add project to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from langmine.web.app import create_app
from langmine.domain.ports import (
    LanguageProcessor, Persistence, TranscriptSource, AudioProcessor,
    TranscriptChunk, MergedSentence,
)
from langmine.domain.models import Video, Sentence, VocabWord


# === Fake ports (same as test_web_api.py) ===

class FakeLanguageProcessor(LanguageProcessor):
    def segment(self, text): return text.split()
    def get_reading(self, text): return " ".join(f"py:{t}" for t in text.split())
    def lookup_word(self, word): return {"definition_de": f"def:{word}", "definition_en": f"def:{word}"}
    def translate_sentence(self, text): return f"[DE] {text}"
    def get_frequency(self, word):
        ranks = {"一般": 1847, "效率": 3412, "爬山": 5000, "管理": 2100}
        return ranks.get(word)
    def is_non_word(self, token): return token in {"的", "了", "吗", "啊", "呢", "吧"}
    def find_known_synonyms(self, word, known_words): return []


class FakePersistence(Persistence):
    def __init__(self):
        self._videos = []
        self._sentences = []
        self._next_vid = 1
        self._next_sid = 1
        self._vocab = []
        self._known_words = {"我们", "早上", "起床", "学习", "我", "爱", "你"}

    def save_video(self, video):
        if video.id is None:
            video.id = self._next_vid; self._next_vid += 1; self._videos.append(video)

    def get_video(self, yt_id):
        for v in self._videos:
            if v.youtube_id == yt_id: return v
        return None

    def list_videos(self): return self._videos
    def video_exists(self, yt_id): return any(v.youtube_id == yt_id for v in self._videos)

    def save_sentences(self, sentences):
        for s in sentences:
            if s.id is None:
                s.id = self._next_sid; self._next_sid += 1
            self._sentences.append(s)

    def get_sentences_by_video(self, vid, status=None):
        results = [s for s in self._sentences if s.video_id == vid]
        if status: results = [s for s in results if s.status == status]
        return results

    def update_sentence(self, s):
        for i, existing in enumerate(self._sentences):
            if existing.id == s.id: self._sentences[i] = s; break

    def get_known_words(self): return self._known_words
    def get_vocab_stats(self): return {"known": len(self._known_words), "learning": 0, "total": len(self._known_words)}
    def mark_word_known(self, w): self._known_words.add(w)
    def mark_word_learning(self, w): pass
    def save_vocab_word(self, w): pass
    def get_vocab_word(self, w): return None
    def get_stash_candidates(self, limit=20):
        return [s for s in self._sentences if s.status == "stashed"][:limit]
    def get_sentences_by_status(self, status):
        return [s for s in self._sentences if s.status == status]
    def reclassify_stashed(self, vid): return 0
    def list_vocab(self, page=1, per_page=200, status=None, search=None, sort="frequency"):
        return [], 0
    def get_sentences_by_word(self, word):
        return [s for s in self._sentences
                if s.unknown_word == word or word in s.text]


class FakeTranscriptSource(TranscriptSource):
    def fetch(self, video_id):
        return [
            TranscriptChunk(text="我们", start_ms=0, duration_ms=500),
            TranscriptChunk(text="一般", start_ms=600, duration_ms=400),
            TranscriptChunk(text="早上", start_ms=1100, duration_ms=400),
            TranscriptChunk(text="七点", start_ms=1600, duration_ms=300),
            TranscriptChunk(text="起床", start_ms=2000, duration_ms=500),
        ]


class FakeAudioProcessor(AudioProcessor):
    def download(self, video_id, output_dir): return f"{output_dir}/{video_id}.mp3"
    def clip(self, *args, **kwargs): return "/tmp/clip.mp3"
    def capture_frame(self, video_id, timestamp_ms, output_dir, sentence_id):
        return f"{output_dir}/frame_{sentence_id}.jpg"


# === Create app ===

persistence = FakePersistence()

# Pre-populate with a video and sentences
video = Video(youtube_id="dQw4w9WgXcQ", title="Test Video", channel="Test Channel")
persistence.save_video(video)

sentences = [
    # i+1 sentence with all fields filled (for edit + screenshot tests)
    Sentence(
        video_id=video.id, start_ms=1000, end_ms=3000,
        text="我们 一般 早上 起床",
        text_segmented="我们 / 一般 / 早上 / 起床",
        pinyin="wǒmen yībān zǎoshang qǐchuáng",
        translation_de="Wir stehen normalerweise morgens auf",
        unknown_word="一般", unknown_word_rank=1847,
        audio_clip_path="/tmp/clip1.mp3",
        screenshot_path="/api/sentences/1/screenshot",
        screenshot_enabled=True,
        status="i1",
    ),
    # i+0 sentence
    Sentence(
        video_id=video.id, start_ms=4000, end_ms=7000,
        text="我 爱 学习",
        text_segmented="我 / 爱 / 学习",
        pinyin="wǒ ài xuéxí",
        translation_de="Ich liebe es zu lernen",
        audio_clip_path="",
        status="i0",
    ),
    # Stashed sentence (i+2: 效率 + 管理 both unknown)
    Sentence(
        video_id=video.id, start_ms=8000, end_ms=12000,
        text="我们 需要 提高 效率 和 管理 水平",
        text_segmented="我们 / 需要 / 提高 / 效率 / 和 / 管理 / 水平",
        pinyin="wǒmen xūyào tígāo xiàolǜ hé guǎnlǐ shuǐpíng",
        translation_de="Wir müssen Effizienz und Management verbessern",
        audio_clip_path="",
        status="stashed",
    ),
]
for s in sentences:
    persistence.save_sentences([s])

app = create_app(
    persistence=persistence,
    language_processor=FakeLanguageProcessor(),
    transcript_source=FakeTranscriptSource(),
    audio_processor=FakeAudioProcessor(),
)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8099, debug=False)
