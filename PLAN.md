# LangMine — YouTube Sentence Mining Tool

> **Status:** Implemented M0–M24 (sentence joining) ✅ — 234 pytest + 51 E2E.
> **This is the original design document.** The actual implementation followed a different milestone numbering (M0–M15 per README). See [README.md](README.md) for current state and [ACCEPTANCE-CHECKLIST.md](ACCEPTANCE-CHECKLIST.md) for the full feature matrix.
> **Languages:** Chinese (v1.2) — Spanish, Korean, Russian planned via `languages/<lang>/` extensions
> **L1:** German
> **Form factor:** Local web app (Python backend → browser tab, no Electron)

---

## Overview

A tool for sentence mining from YouTube videos. Paste a URL, get every sentence extracted with audio clips, screenshots, pinyin, translation, and word breakdown. The i+1 filter surfaces only sentences with exactly one unknown word. Curate (keep/delete), stash harder content for later, then export directly to Anki.

---

## Pipeline

```
YouTube URL
    │
    ▼
[Transcript Extraction]   youtube-transcript-api → raw subtitle chunks w/ timestamps
[Audio Download]          yt-dlp → full MP3
[Sentence Merging]        Time-gap heuristic (500ms default) → merged sentences
[Frame Extraction]        ffmpeg frame grab at sentence midpoint → sentence_042.jpg
[Audio Clipping]          ffmpeg trim +250ms/-300ms padding → sentence_042.mp3
    │
    ▼
[Chinese NLP]             (via LanguageProcessor plugin interface)
    jieba                 → word segmentation
    pypinyin              → pinyin
    CC-CEDICT             → word definitions (German preferred, English fallback)
    Google Translate      → sentence-level ZH→DE
    SUBTLEX-CH            → word frequency ranking
    │
    ▼
[i+1 Classification]
    1. Segment → remove non-words (particles, numbers, names) → count unknowns
    2. unknown_count == 1 AND unknown word ∈ known vocab? → status = 'i1'
    3. unknown_count == 0                               → status = 'i0'  (skip)
    4. unknown_count >= 2                               → status = 'stashed'
    5. Sort i+1 candidates by SUBTLEX-CH frequency, cap at 20
    │
    ▼
[Curation UI]
    Card view: audio + image (togglable) + text + pinyin + translation
    Unknown word highlighted with frequency tier (🔥/⭐/💎)
    Known synonyms from CC-CEDICT shown if available
    Actions: Keep / I Know This / Delete / Edit / Toggle screenshot
    │
    ▼
[Stash]                    i+2+ sentences stored for future
    Re-scanned when words are marked as known
    Same 20-card cap + frequency sort
    User visits deliberately (separate tab)
    │
    ▼
[Anki Export]              One-way push via AnkiConnect (localhost:8765)
    Note type: "LangMine Sentence" (auto-created)
    Front: audio clip + screenshot
    Back: 汉字 + pinyin + German translation + word breakdown + source
```

---

## Architecture Decisions (from grilling)

### Sentence Detection
**Decision:** Pause-based merging. Merge subtitle chunks until the time gap exceeds 500ms (configurable). Spaces in transcript treated as soft boundaries. No reliance on punctuation — works for Chinese content that lacks it.

### i+1 Word Rules
**Decision:** jieba segments, then filter out non-words before counting:
| Category | Counts as word? |
|----------|----------------|
| Particles (的, 了, 吗, 呢, 吧, 啊) | No |
| Result complements (看见, 吃完) | Yes, as one word |
| Multi-char compounds (为什么, 可以) | Yes, as one word |
| Numbers/dates (七点, 三月) | No |
| Names/places (张三, 北京) | No |

Filtered-out categories don't affect i+1 counting. Manual re-segmentation available in UI.

### Translation
**Decision:** Google Translate for sentence-level (ZH→DE), CC-CEDICT for word-level with English fallback. DeepL as optional upgrade in settings. User can manually correct any translation in the curation UI.

### Screenshots
**Decision:** Extracted for every sentence (ffmpeg frame grab at midpoint). Per-card toggle in curation UI — user decides whether to include on the final Anki card. Toggled-off screenshots deleted immediately.

### Audio Padding
**Decision:** +250ms before subtitle start, +300ms after subtitle end. Configurable.

### Processing Model
**Decision:** Single video at a time. Video library sidebar tracks already-mined videos (grayed out). No playlist support in v1.

### First-Run Handling
**Decision:** i+1 candidates sub-sampled to 20 per video, sorted by SUBTLEX-CH frequency (highest first). Cap is configurable. User sees the most useful unknown words first.

### Stash Behavior
**Decision:** i+2+ sentences saved as `stashed`. Re-scanned when words are marked as known — if a stashed sentence drops to i+1, it appears in the Stash tab. User visits stash deliberately. Same 20-card cap, frequency-sorted. Newly-available indicator on videos with fresh candidates.

### Frequency Indicator
**Decision:** Three-tier visual indicator next to unknown word:
| Tier | Rank | Icon | Meaning |
|------|------|------|---------|
| Core | 1–2,000 | 🔥 | High priority — learn now |
| Useful | 2,001–6,000 | ⭐ | Worth learning |
| Rare | 6,000+ | 💎 | Niche — skip unless interesting |

### Synonyms
**Decision:** CC-CEDICT `same as` / `see also` annotations only. Cross-referenced against known vocab. Displayed as "Similar to words you know: X" on the card. No second dictionary, no embedding model in v1.

### Architecture: Language Plugins
**Decision:** `LanguageProcessor` abstract class from day one. Methods: `segment()`, `get_pinyin_or_reading()`, `lookup_word()`, `translate_sentence()`, `get_frequency()`, `is_non_word()`, `find_known_synonyms()`. `ChineseProcessor` implements it first. Spanish, Korean, Russian as future plugins.

### Desktop Shell
**Decision:** No Electron. Browser tab only — Flask (or FastAPI) serves the UI at `http://localhost:8080`. Reduces complexity significantly.

### Media Retention
**Decision:** Keep all media forever for kept/exported sentences. Delete audio clip + screenshot when user hits "Delete" on a sentence. Delete screenshot when toggled off on a kept card. No background cleanup. Video library metadata (sentences, timestamps, status) always preserved.

### Anki Integration
**Decision:** One-way push via AnkiConnect in v1. Two-way sync (Anki maturity → auto-promote to "known") is v1.5.

### Known Vocabulary Bootstrap
**Decision:** HSK 1-3 (~600 words) seeded as known. "I Know This" button on cards to rapidly grow vocab. Kept sentences auto-mark unknown word as "learning."

---

## Database Schema (SQLite)

```sql
videos (
    id INTEGER PRIMARY KEY,
    youtube_id TEXT UNIQUE,
    title TEXT,
    channel TEXT,
    duration_sec INTEGER,
    transcript_json TEXT,    -- raw transcript with timestamps
    audio_path TEXT,         -- full MP3 file path
    processed_at DATETIME
)

sentences (
    id INTEGER PRIMARY KEY,
    video_id INTEGER REFERENCES videos(id),
    start_ms INTEGER,
    end_ms INTEGER,
    text TEXT,               -- original Chinese
    text_segmented TEXT,     -- jieba: "我们 / 一般 / 早上 / 七点 / 起床"
    non_words_json TEXT,     -- filtered-out tokens: ["我们","早上","七点"]
    pinyin TEXT,             -- "wǒmen yībān zǎoshang..."
    translation_de TEXT,     -- German translation (user-editable)
    unknown_word TEXT,       -- the i+1 target (NULL for i0/stashed)
    unknown_word_rank INTEGER,  -- SUBTLEX-CH frequency rank
    known_synonyms_json TEXT,   -- ["经常"] — known words that are synonyms
    audio_clip_path TEXT,
    screenshot_path TEXT,
    screenshot_enabled INTEGER DEFAULT 1,  -- user toggled on/off during curation
    status TEXT DEFAULT 'new'  -- i1 | i0 | stashed | kept | deleted | exported
    -- i1: visible in curation (i+1 candidate)
    -- i0: all words known (shown muted, delete-only)
    -- stashed: i+2+, waiting in stash
    -- kept: user chose to keep (ready for export)
    -- deleted: user discarded (media deleted)
    -- exported: pushed to Anki
)

vocab (
    id INTEGER PRIMARY KEY,
    word_simplified TEXT,
    word_traditional TEXT,
    pinyin TEXT,
    definition_de TEXT,
    hsk_level INTEGER,        -- NULL if not in HSK, 1-6
    frequency_rank INTEGER,   -- from SUBTLEX-CH
    status TEXT DEFAULT 'known'  -- known | learning
    -- known: confirmed known (HSK bootstrap, "I Know This", mature in Anki)
    -- learning: from a kept sentence, not yet mature
)
```

---

## UI Layout

```
┌───────────────────────────────────────────────────────────┐
│  LangMine                                        [⚙ Settings]│
├──────────┬────────────────────────────────────────────────┤
│          │                                                │
│  📹      │  ┌─ Beijing Street Interview ──────────────┐  │
│  Videos  │  │                                          │  │
│          │  │  ▶ 00:42  我们一般早上七点起床             │  │
│  ▸ 北京   │  │     wǒmen yībān zǎoshang qī diǎn...     │  │
│    采访   │  │     Wir stehen normalerweise um 7 Uhr... │  │
│          │  │     🆕 一般  🔥 #1,847                    │  │
│  ▸ 美食   │  │     Similar to: 通常                      │  │
│    探店✓  │  │     🖼 [x] Include screenshot            │  │
│          │  │                  [✓ Keep] [✗ Delete]      │  │
│  ▸ 旅行   │  │                     [I know this]         │  │
│    vlog   │  └──────────────────────────────────────────┘  │
│          │                                                │
│  + Add   │  ┌────────────────────────────────────────┐   │
│          │  │ ▶ 01:15  然后我们去吃早餐                │   │
│  ─────── │  │     All words known (i+0)               │   │
│  📥      │  │                           [✗ Delete]    │   │
│  Stash   │  └────────────────────────────────────────┘   │
│  (3 new) │                                                │
│          │  ───── 8 sentences kept ─────────────────────  │
│  ─────── │  [Export to Anki]                              │
│  📚      │                                                │
│  Vocab   │                                                │
│  645     │                                                │
│  known   │                                                │
└──────────┴────────────────────────────────────────────────┘
```

### UI States Per Sentence

| Status | Display | Actions |
|--------|---------|---------|
| **i+1** | Full card, unknown word highlighted with frequency tier | Keep / Delete / I Know This / Edit / Toggle screenshot |
| **i+0** | Muted card, "all words known" badge | Delete only |
| **stashed** | In stash tab only. Shown when drops to i+1. | Keep / Delete / I Know This |
| **kept** | Green border, "kept" badge, appears below curation area | Un-keep / Edit / Toggle screenshot |
| **exported** | Blue border, "in Anki" badge | View only |

### Manual Override Features
- **Re-segment**: Click-drag to merge/split words (updates i+1 classification)
- **Fix pinyin**: Click to edit (for 多音字 like 了 le/liǎo)
- **Edit translation**: Click German text to edit
- **Toggle screenshot**: Checkbox on each card

### Tabs
- **Videos** (default): Video library + curation for selected video
- **Stash**: i+2+ sentences that have dropped to i+1, across all videos
- **Vocab**: Searchable list of known/learning words with stats

---

## Anki Export (AnkiConnect)

### Note Type: "LangMine Sentence"

| Field | Content |
|-------|---------|
| `front_audio` | `[sound:sentence_042.mp3]` |
| `front_image` | `<img src="sentence_042.jpg">` (only if screenshot_enabled=1) |
| `sentence` | 我们一般早上七点起床 |
| `pinyin` | wǒmen yībān zǎoshang qī diǎn qǐchuáng |
| `translation` | Wir stehen normalerweise um 7 Uhr auf |
| `word_breakdown` | 我们/wir · 一般🆕/normalerweise · 早上/morgens · 七点/7 Uhr · 起床/aufstehen |
| `source` | Beijing Street Interview (youtube.com/watch?v=...) |

### Card Template

```
Front:  [audio auto-plays] + [screenshot if included]
Back:   {{sentence}}
        {{pinyin}}
        {{translation}}
        ─────────────────
        {{word_breakdown}}
        ─────────────────
        {{source}}
```

### Export Flow
1. User clicks "Export to Anki"
2. Check AnkiConnect reachable at `localhost:8765`
3. Create note type "LangMine Sentence" if not exists
4. Copy media files (audio clips, screenshots) to Anki `collection.media/`
5. Create notes in deck "Chinese::Sentence Mining" (configurable)
6. Mark exported sentences as status='exported'
7. Auto-mark unknown words as status='learning' in vocab DB

---

## Language Plugin Interface

```python
class LanguageProcessor(ABC):
    """Each target language implements this interface."""

    @abstractmethod
    def segment(self, text: str) -> list[str]:
        """Segment text into words/tokens."""

    @abstractmethod
    def get_reading(self, text: str) -> str:
        """Phonetic reading: pinyin for zh, IPA for es, etc."""

    @abstractmethod
    def lookup_word(self, word: str) -> WordDef | None:
        """Dictionary lookup. Returns definition in target language (DE)."""

    @abstractmethod
    def translate_sentence(self, text: str) -> str:
        """Sentence-level MT. Returns German translation."""

    @abstractmethod
    def get_frequency(self, word: str) -> int | None:
        """Frequency rank (higher = more common). None if unknown."""

    @abstractmethod
    def is_non_word(self, token: str) -> bool:
        """True if this token should be excluded from i+1 counting
        (particles, numbers, names, etc.)."""

    @abstractmethod
    def find_known_synonyms(
        self, word: str, known_words: set[str]
    ) -> list[str]:
        """Return any known synonyms of `word`."""

    # Future methods (v1.5+)
    # def lemmatize(self, word: str) -> str: ...
    # def get_pitch_accent(self, word: str) -> str: ...
```

### ChineseProcessor (v1)
- `segment()`: jieba.cut
- `get_reading()`: pypinyin
- `lookup_word()`: CC-CEDICT via python-cedict (DE preferred, EN fallback)
- `translate_sentence()`: Google Translate API
- `get_frequency()`: SUBTLEX-CH lookup
- `is_non_word()`: particle list + number/date regex + name heuristic (not in CC-CEDICT + common surname chars)
- `find_known_synonyms()`: CC-CEDICT `same as` / `see also` annotations

### Future Processors
- **SpanishProcessor**: spaCy (es_core_news_sm), SpanishDict/ES→DE dict, lemmatization for i+1 matching
- **KoreanProcessor**: KoNLPy/Mecab-ko, KRDICT, romanization
- **RussianProcessor**: spaCy (ru_core_news_sm), stress marks, lemmatization

---

## Configuration

```yaml
# ~/.langmine/config.yaml
anki:
  anki_connect_url: "http://localhost:8765"
  deck_name: "Chinese::Sentence Mining"
  note_type: "LangMine Sentence"

languages:
  source: "zh"
  target: "de"

nlp:
  translation_api: "google"   # google, deepl
  deepl_api_key: ""           # only needed for deepl

mining:
  sentence_gap_ms: 500        # max gap between subtitle chunks for merging
  audio_pad_before_ms: 250
  audio_pad_after_ms: 300
  max_cards_per_video: 20     # cap for i+1 candidates per video
  max_stash_cards: 20         # cap for stash re-scan

vocab:
  hsk_bootstrap: 3            # seed HSK levels 1-3 as known

paths:
  data_dir: "~/.langmine/"
  media_dir: "~/.langmine/media/"
```

---

## Implementation Milestones (Vertical Slices)

> **Methodology:** Strict TDD on every milestone. Red → Green → Refactor.
> No production code without a failing test first.
> Each milestone is shippable — you can stop at any point and have a usable tool.

---

### M0: Project Scaffold (TDD from day one)

**Goal:** Runnable Python project with test infrastructure, config, and database. Foundation for M1.

- [ ] `pyproject.toml` with dependencies (yt-dlp, youtube-transcript-api, jieba, pypinyin, flask, sqlite3, pytest)
- [ ] Project structure: `langmine/` package, `tests/`, `data/`
- [ ] Config loading: read `~/.langmine/config.yaml` with defaults, create on first run
- [ ] SQLite schema creation with migration system (version-based)
- [ ] `LanguageProcessor` abstract base class + registry
- [ ] Entry point: `langmine` (web server)
- [ ] TDD infrastructure: `pytest` configured, test DB fixture, first passing test (config loads)

**Acceptance:** `pip install -e . && langmine --version && pytest tests/ -v` all green.

---

### M1: Mine One Sentence (first vertical slice)

**Goal:** End-to-end pipeline for a single sentence. YouTube URL → one merged sentence → audio clip. Prove the core loop works.

**Tests (write first, watch fail):**
- [ ] Transcript fetcher returns subtitle chunks from a video
- [ ] Sentence merger combines adjacent chunks ≤500ms apart
- [ ] Audio downloader fetches MP3 from yt-dlp
- [ ] Audio clipper trims a segment with correct padding (+250ms/-300ms)
- [ ] Integration: `pipeline.extract_one_sentence(url)` returns `{text, start_ms, end_ms, audio_path}`

**Implementation:**
- [ ] `youtube-transcript-api` integration: fetch subtitle chunks
- [ ] Sentence merger: time-gap heuristic (500ms), spaces as soft boundaries
- [ ] yt-dlp audio download: full MP3, cached per video
- [ ] ffmpeg audio clipping: trim first merged sentence with padding
- [ ] Pipeline produces sentences with audio clips

**Acceptance:** Sentences with audio clips are produced.

---

### M2: Classify All Sentences

**Goal:** Full transcript processing with i+1 classification. Every sentence in a video is extracted, segmented, and tagged.

**Tests (write first, watch fail):**
- [ ] Full sentence merger: all subtitle chunks → all merged sentences
- [ ] jieba segmentation: `"我们一般早上七点起床"` → `["我们", "一般", "早上", "七点", "起床"]`
- [ ] Non-word filter: particles (的,了,吗,吧,呢,啊), numbers/dates, names excluded
- [ ] HSK 1-3 bootstrap lookup: known words correctly identified
- [ ] i+1 classification: one unknown → `i1`, zero → `i0`, two+ → `stashed`
- [ ] Frequency sorting: i+1 candidates sorted by SUBTLEX-CH rank
- [ ] 20-card cap: only top 20 i+1 returned per video
- [ ] `pipeline.process_video(url)` returns `{i1_candidates: [...], i0_count: N, stash_count: N}`

**Implementation:**
- [ ] Full sentence merger on all chunks
- [ ] `ChineseProcessor.segment()` — jieba integration
- [ ] `ChineseProcessor.is_non_word()` — particle list + number/date regex + name heuristic
- [ ] `ChineseProcessor.get_frequency()` — SUBTLEX-CH data file + lookup
- [ ] HSK 1-3 word lists loaded from bundled CSV, seeded into vocab DB as `known`
- [ ] CC-CEDICT lookup for each HSK word: German preferred, English fallback
- [ ] i+1 classification pipeline: segment → filter non-words → count unknowns → classify
- [ ] Frequency cap: sort i+1 by SUBTLEX-CH, cap at 20

**Acceptance:** Process a video. i+1 sentences have exactly one unknown non-HSK-3 word. i+0 sentences exist. Stash shows i+2+ count. Frequency cap respected.

---

### M3: Curate in Browser

**Goal:** Minimal web UI for keep/delete curation. First visual experience.

**Tests (write first, watch fail):**
- [ ] `POST /api/videos` — accepts URL, triggers pipeline, returns video metadata
- [ ] `GET /api/videos/<id>/sentences?status=i1` — returns i+1 cards with text + audio URL
- [ ] `PUT /api/sentences/<id>` — updates status to `kept` or `deleted`
- [ ] `DELETE` sets status → media files deleted, sentence text/metadata preserved
- [ ] `POST /api/sentences/<id>/mark-known` — unknown word → `known`, stash re-scanned
- [ ] Frontend: video input form → submit → sentence cards appear
- [ ] Frontend: Keep / Delete / "I Know This" buttons with status feedback
- [ ] Frontend: audio play button per card
- [ ] Frontend: kept sentence counter below cards

**Implementation:**
- [ ] Flask/FastAPI backend with CORS
- [ ] API endpoints: videos CRUD, sentences query + update, mark-known with stash re-scan
- [ ] Video processing triggered synchronously (with polling for UI)
- [ ] Minimal SPA (vanilla HTML/JS or lightweight framework)
- [ ] Sentence cards with text, audio player, action buttons
- [ ] Video library sidebar: list processed videos, gray out already-mined
- [ ] App starts on port 8080
**Acceptance:** `langmine` → open `localhost:8080`


---

### M4: Translate & Understand

**Goal:** Full card content: pinyin, German translation, word definitions, synonym hints.

**Tests (write first, watch fail):**
- [ ] `ChineseProcessor.translate_sentence()` — Google Translate API call (ZH→DE), mocked for tests
- [ ] `ChineseProcessor.lookup_word()` — CC-CEDICT lookup returns German/English definition
- [ ] `ChineseProcessor.get_reading()` — pypinyin returns correct pinyin
- [ ] `ChineseProcessor.find_known_synonyms()` — CC-CEDICT `same as` annotation cross-ref with known vocab
- [ ] Translation caching: second call for same sentence returns cached value
- [ ] Frontend: cards display pinyin, translation, word breakdown, frequency badge, known synonyms

**Implementation:**
- [ ] Google Translate API integration (ZH→DE)
- [ ] CC-CEDICT word lookup (DE preferred, EN fallback)
- [ ] pypinyin reading generation
- [ ] Synonym detection from CC-CEDICT `same as` / `see also` annotations
- [ ] Translation cache in DB (`translation_de` field)
- [ ] Frequency tier badges: 🔥 (1–2,000), ⭐ (2,001–6,000), 💎 (6,000+)
- [ ] Word breakdown rendering: "我们/wir · 一般🆕/normalerweise · 早上/morgens · ..."
- [ ] Known synonym display: "Similar to: 经常" when applicable

**Acceptance:** Curate a video in browser. Every card shows pinyin + German translation + word breakdown. Unknown word has frequency badge. Known synonyms appear where CC-CEDICT has `same as` annotations.

---

### M5: Export to Anki

**Goal:** Push curated sentences to Anki. This is the payoff milestone.

**Tests (write first, watch fail):**
- [ ] AnkiConnect reachability check
- [ ] Note type "LangMine Sentence" auto-created if missing
- [ ] Media files copied to Anki `collection.media/`
- [ ] Note created in correct deck with all fields populated
- [ ] Duplicate detection: same youtube_id + start_ms → skip
- [ ] Exported sentences marked `status='exported'`
- [ ] Unknown words marked `status='learning'` in vocab DB

**Implementation:**
- [ ] AnkiConnect API client (localhost:8765)
- [ ] Note type creation with proper field ordering
- [ ] Media file copy to `collection.media/`
- [ ] Note creation in deck "Chinese::Sentence Mining" (configurable)
- [ ] Card template: front = audio + screenshot, back = sentence + pinyin + translation + breakdown + source
- [ ] Export button in UI with progress indicator
- [ ] Export summary: "12 cards added, 0 duplicates, 0 errors"

**Acceptance:** Click "Export to Anki" with Anki running. Open Anki — cards present with audio, screenshots (for kept cards), all fields filled. Export again — zero duplicates. Words marked "learning" in vocab.

---

### M6: Stash & Screenshots

**Goal:** Stash system for i+2+ sentences + visual context on every card.

**Tests (write first, watch fail):**
- [ ] Stash classification: i+2+ sentences stored as `status='stashed'`
- [ ] Stash re-scan: marking word as known re-classifies stashed sentences
- [ ] Stash re-scan: sentences dropping to i+1 appear in stash query, sorted by frequency, capped at 20
- [ ] ffmpeg frame grab at sentence midpoint
- [ ] Screenshot can be toggled on/off per card
- [ ] Toggling off deletes the screenshot file

**Implementation:**
- [ ] Stash classification in pipeline (already in M2 schema, now wired to UI)
- [ ] Stash re-scan trigger: on `mark-known`, re-filter all stashed sentences
- [ ] Stash tab in UI: same card layout for newly-i+1 candidates
- [ ] "Newly available" badge on videos with fresh stash candidates
- [ ] ffmpeg frame extraction at `start_ms + (end_ms - start_ms)/2`, JPEG ~60-80KB
- [ ] `screenshot_enabled` toggle per card in UI + DB
- [ ] Screenshot delete on toggle-off or sentence delete

**Acceptance:** After marking several words as known, stash tab shows new i+1 candidates. Screenshots appear on all cards. Toggling screenshot off on a card removes the image file and hides it from Anki export preview.

---

### M7: Polish & Edit

**Goal:** Manual overrides, error handling, empty states. Production-quality v1.

**Tests (write first, watch fail):**
- [ ] Edit pinyin: PUT updates `sentences.pinyin`, persisted to DB
- [ ] Edit translation: PUT updates `sentences.translation_de`, re-renders card
- [ ] Edit segmentation: re-segment triggers re-classification (i+1 may change)
- [ ] Error: invalid YouTube URL → user-friendly error in UI
- [ ] Error: transcript unavailable → message with suggestion
- [ ] Error: AnkiConnect unreachable → disable export button with explanation
- [ ] Error: audio download failed → grace ful degradation (text-only card)
- [ ] Empty states: "No videos yet", "Stash is empty", "All caught up!"
- [ ] Loading states: spinner during processing, progress indicator
- [ ] Confirmation dialog on delete

**Implementation:**
- [ ] Click-to-edit on pinyin, translation, segmentation with save on blur
- [ ] Re-segmentation triggers full re-classification pipeline for that sentence
- [ ] Loading spinners + progress bar during video processing
- [ ] Error boundaries: every error path has a user-facing message
- [ ] Empty state components for videos, stash, vocab
- [ ] Confirmation dialog: "Delete this sentence? Audio + screenshot will be removed."
- [ ] Settings page: all config values editable with save
- [ ] Dark/light theme toggle
- [ ] "Re-mine" button on processed videos (re-classifies with updated vocab)

**Acceptance:** Every error path shows a helpful message. Manual edits persist and affect i+1 classification. No blank screens, no crashes. Settings page functional.

---

## Future Milestones (v1.1+)

- **M8: Spanish NLP pipeline** — SpanishProcessor with spaCy lemmatization
- **M9: Anki two-way sync** — read mature cards from Anki, auto-promote words to "known"
- **M10: Word embedding synonyms** — fastText Chinese word vectors for broader synonym coverage
- **M11: Auto-generated subtitle support** — pause-only heuristic, no punctuation fallback
- **M12: Korean / Russian processors**
- **M13: Netflix subtitle import** — .srt file upload pipeline, bypass YouTube entirely

---

## Data Files (bundled with app)

```
langmine/
  data/
    hsk/
      hsk1.csv          # word, pinyin, definition_en
      hsk2.csv
      hsk3.csv
    subtlex-ch/
      SUBTLEX-CH.txt     # word, frequency, WCount, W-CD, ...
    cedict/
      cedict_ts.u8       # CC-CEDICT dictionary file
```

---

## Open Questions (deferred)

1. **Auto-generated subtitle support**: Skipped for v1. Manual transcripts only. Pause-only merge works but auto-gen timestamps are worse and need separate tuning.
2. **Anki two-way sync**: Valuable but adds complexity. Deferred to v1.5.
3. **German CC-CEDICT coverage**: Most common words will have German entries. Rare words fall back to English. Acceptable.
4. **Embedding-based synonyms**: CC-CEDICT `same as` annotations are sparse. fastText is the real solution but adds a ~300MB model dependency. Deferred to v1.5.
