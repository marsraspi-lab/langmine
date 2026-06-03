# LangMine

YouTube sentence mining for language learning. Extract sentences with audio from YouTube videos, filter by vocabulary level (i+1), curate in a browser, and send flashcards directly to Anki via AnkiConnect.

**Status:** v1.7.2 — M0–M26 shipped. 245 pytest + 57 E2E. All tests pass.

## Requirements

- **Python 3.11+**
- **ffmpeg** — for audio processing and clipping (auto-downloaded via setup script if missing)
- **Anki** + **AnkiConnect addon** (ID: 2055492159) — for flashcard export
- **Node.js 26+** — for building the Svelte frontend

### Installing ffmpeg

LangMine bundles its own static ffmpeg binaries. Run the setup script once:

```bash
./scripts/setup-ffmpeg.sh
```

This downloads static ARM64/x86_64 ffmpeg + ffprobe to `bin/`. If you prefer system ffmpeg:

| OS | Command |
|----|---------|
| macOS | `brew install ffmpeg` |
| Ubuntu/Debian | `sudo apt install ffmpeg` |
| Windows | `winget install ffmpeg` or [ffmpeg.org](https://ffmpeg.org/download.html) |

LangMine uses the project binaries automatically if present, falling back to system PATH.

---

## Docker Quick Start (recommended)

No Python, Node, or ffmpeg install needed — just Docker.

### With Docker Compose

```bash
git clone https://github.com/marsraspi-lab/langmine.git
cd langmine
docker compose up
# → http://localhost:8080
```

This mounts `~/.langmine` for persistence and configures
`host.docker.internal` so AnkiConnect on the host works automatically.

### With docker run

```bash
docker run -p 8080:8080 \
  -v ~/.langmine:/root/.langmine \
  --add-host=host.docker.internal:host-gateway \
  marsraspi-lab/langmine:latest
```

The `--add-host` flag is required for AnkiConnect on Linux (Docker Desktop
for Mac/Windows provides `host.docker.internal` automatically).

### Build from source

```bash
git clone https://github.com/marsraspi-lab/langmine.git
cd langmine
docker build --build-arg VERSION=1.2.0 -t langmine:1.2.0 .
docker run -p 8080:8080 -v ~/.langmine:/root/.langmine \
  --add-host=host.docker.internal:host-gateway \
  langmine:1.2.0
```

---

## Installation

```bash
git clone https://github.com/marsraspi-lab/langmine.git
cd langmine
pip install -e ".[dev]"

# Download ffmpeg binaries (one-time)
./scripts/setup-ffmpeg.sh

# Build the frontend
cd src/langmine/web/frontend && npm install && npm run build && cd -
```

This installs LangMine in editable mode with all Python dependencies:
`yt-dlp`, `jieba`, `pypinyin`, `deep-translator`, `flask`, `pyyaml`, `requests`, `pytest`, `pytest-cov`

Chinese language processing uses `jieba` (segmentation), `pypinyin` (reading), and CC-CEDICT. Other languages use their own NLP toolchain — see `languages/` directory.

---

## Usage

### Start the web UI

```bash
langmine                  # → http://127.0.0.1:8080
langmine --port 9000      # custom port
```

The web UI lets you browse mined sentences, edit readings/translations/segmentation inline, keep or delete sentences, mark words as known, learning, or ignored, and configure settings. Ignored words (proper names, noise) are excluded from the i+1 unknown count, and words marked ignored trigger automatic stash reclassification — sentences with only one remaining unknown word are promoted to i+1. Use the **language selector** in the top bar to switch between languages — each language has its own isolated vocabulary, sentences, and videos.

### Export to Anki

Use the **📦 Export to Anki** button in the sidebar. Check "⚡ Update card templates" to push template changes from the language extension (`languages/<lang>/anki/`).

Anki must be running with the AnkiConnect addon installed.

### View version

```bash
langmine --version                  # e.g. "langmine 1.7.2"
```

---

## Configuration

On first run, LangMine creates `~/.langmine/config.yaml`. All values can also be edited from the **⚙️ Settings** page in the web UI.

```yaml
anki:
  anki_connect_url: "http://host.docker.internal:8765"

languages:
  source: "zh"        # language code for mining — use the top-bar selector in web UI
  target: "de"        # translation target language

nlp:
  translation_api: "google"

mining:
  sentence_gap_ms: 500        # max gap between subtitle chunks when merging
  audio_pad_before_ms: 250    # padding before sentence audio
  audio_pad_after_ms: 300     # padding after sentence audio
  max_cards_per_video: 20     # i+1 candidates per video
  max_stash_cards: 20         # stash re-scan candidates

storage:
  data_dir: "~/.langmine/data"   # audio clips, screenshots, downloads

network:
  user_agent: ""                # custom User-Agent (e.g. "Mozilla/5.0 ...")
```

**Anki card templates** (`deck_name`, `note_type`, CSS, front/back HTML) are **no longer in config.yaml**. They live as files per language under `languages/<lang>/anki/`. To customize card appearance, edit the HTML/CSS files in the language directory, check "⚡ Update card templates", and export.

See **[docs/TEMPLATES.md](docs/TEMPLATES.md)** for card template customization — available fields, Mustache conditionals, and Anki-side editing.

---

## Multi-Language Support

LangMine supports multiple source languages. Each language has its own:

- **Data isolation** — sentences, videos, and vocabulary are partitioned by `language_code` in the database. Switching languages filters data — nothing is purged.
- **NLP pipeline** — segmentation, phonetics, dictionary, and frequency adapters live in `languages/<lang>/`.
- **Anki templates** — card HTML/CSS live in `languages/<lang>/anki/{basic,cloze}/`.

### Changing language

Use the **dropdown selector** in the web UI top bar. The switch calls `PUT /api/config` with `source_language`, then reloads all data scoped to the new language.

GET `/api/languages` returns available language codes and display names.

### Currently supported

| Code | Language | Directory |
|------|----------|-----------|
| `zh` | 中文 (Chinese) | `languages/chinese/` |

Planned: `es` (Spanish), `ko` (Korean), `ru` (Russian).

---

## How It Works

```
YouTube URL → transcript → merge subtitle chunks into sentences
             → download full audio → clip per-sentence with padding
             → capture screenshot at sentence midpoint
             → Language NLP (segmentation, reading, dictionary,
                translation, frequency ranking)
             → i+1 filter (one unknown word = learnable)
             → stash i+2+ sentences for later
             → curate in browser (keep/delete/I-know-this, mark known/learning/ignored,
                edit reading/translation/segmentation)
             → ignored words trigger stash reclassification (promote i+1 candidates)
             → dark/light theme toggle
             → switch language from top bar (isolated data per language)
             → export to Anki via AnkiConnect (cards with audio + screenshots)
```

---

## Architecture

Hexagonal (ports & adapters). Domain logic depends on abstract ports — never on YouTube, ffmpeg, or SQLite directly. Swap adapters without touching domain code.

```
src/langmine/
├── domain/
│   ├── ports.py          # Abstract interfaces (Persistence, Translator, etc.)
│   ├── models.py         # Pure dataclasses + frequency tier logic
│   ├── classifier.py     # i+1 classification engine
│   └── services/         # Language-agnostic service logic
├── adapters/
│   ├── sqlite_persistence.py   # SQLite behind Persistence port
│   ├── youtube_transcript.py   # YouTube behind TranscriptSource port
│   ├── ytdlp_audio.py          # yt-dlp+ffmpeg behind AudioProcessor port
│   ├── google_translate.py     # deep-translator behind Translator port
│   └── anki_connect.py         # AnkiConnect behind AnkiExporter port
├── languages/
│   └── chinese/
│       ├── __init__.py         # MANIFEST + get_anki_templates() + exports
│       ├── service.py          # ChineseLanguageService (segment, reading, classify)
│       ├── dictionary.py       # CcCedictAdapter (CC-CEDICT, 125K entries)
│       ├── frequency.py        # SubtlexChAdapter + JiebaFrequencyAdapter
│       ├── hsk_data.py         # HSK proficiency levels
│       ├── anki/               # Card templates as files
│       │   ├── basic/{front.html, back.html, css.css}
│       │   └── cloze/{front.html, back.html, css.css}
│       └── data/               # CC-CEDICT dictionary + SUBTLEX corpus
├── language_factory.py   # Single switch point for language loading
├── web/
│   ├── app.py            # Flask app factory (port injection)
│   ├── routes.py         # REST API endpoints (GET /api/languages, etc.)
│   ├── static/           # Built Svelte output (served by Flask)
│   └── frontend/         # Svelte 5 + Vite source (language-agnostic + selector)
├── pipeline.py           # End-to-end mining (accepts ports)
├── config.py             # YAML config with defaults (templates removed)
├── audio.py              # yt-dlp/ffmpeg helpers (uses project binaries)
└── bin/                  # Static ffmpeg/ffprobe (downloaded via setup script)
```

The cardinal rule: `domain/` never imports from `adapters/` or `web/`. Similarly, `domain/` and `web/` never import from `languages/` — only `language_factory.py` touches language packages.

### API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/videos` | List videos (filtered by `language_code`) |
| `GET /api/videos/<id>/sentences` | Sentences for a video |
| `GET /api/videos/<id>/transcript` | Full reading-mode transcript |
| `PATCH /api/sentences/<id>` | Update sentence status/fields |
| `PATCH /api/sentences/<id>/iknowthis` | Mark word as known |
| `GET /api/stats` | Vocabulary stats |
| `GET /api/vocab` | Vocab listing (filter by status: known/learning/ignored) |
| `GET /api/vocab/<word>` | Single word detail with example sentences |
| `PATCH /api/vocab/<word>` | Update word status (known/learning/ignored/unknown) |
| `GET /api/config` | Current config (no Anki templates) |
| `PUT /api/config` | Update config |
| `GET /api/languages` | Available languages `[{code, name}]` |
| `GET /api/version` | Installed version |
| `POST /api/videos/mine` | Mine a YouTube video |
| `POST /api/export/anki` | Export sentences to Anki |

### Adding a Language

Create `languages/<code>/` with 5 files + template directory:

```
languages/spanish/
├── __init__.py           # MANIFEST dict + get_anki_templates() + exports
├── service.py            # SpanishLanguageService(LanguageProcessor)
├── dictionary.py         # SpanishDict adapter (Dictionary port)
├── frequency.py          # SUBTLEX-ES adapter (FrequencySource port)
└── anki/
    ├── basic/{front.html, back.html, css.css}
    └── cloze/{front.html, back.html, css.css}
```

The `__init__.py` must expose:
```python
MANIFEST = {
    "name": "Español",
    "deck_name": "Spanish::Sentence Mining",
    "note_type": "LangMine Spanish Sentence",
    "cloze_note_type": "LangMine Spanish Cloze",
}

def get_anki_templates():
    """Load card templates from anki/ directory."""
    ...
```

Then add to `language_factory.py`:
```python
case "es":
    from langmine.languages.spanish import SpanishLanguageService, SpanishDict, SubtlexEsAdapter
    return SpanishLanguageService(SpanishDict(), GoogleTranslateAdapter(), SubtlexEsAdapter())
```

Also add to the `LANGUAGES` list in `language_factory.py`:
```python
{"code": "es", "name": "Spanish"},
```

No changes needed in `domain/`, `web/`, `adapters/`, or `pipeline.py` — the factory handles everything.
 The Svelte frontend is fully language-agnostic — it renders whatever JSON the API returns. The language selector auto-populates from `GET /api/languages`.

### Frequency tiers

Frequency rank → badge mapping is pure domain logic in `domain/models.py`:

| Tier | Rank | Icon | Meaning |
|------|------|------|---------|
| Core | 1–2,000 | 🔥 | High priority — learn now |
| Useful | 2,001–6,000 | ⭐ | Worth learning |
| Rare | 6,000+ | 💎 | Niche — skip unless interesting |

---

## Milestones

| # | Milestone | Status |
|---|-----------|--------|
| M0 | Project Scaffold | ✅ |
| M1 | Mine One Sentence | ✅ |
| M2 | Classify All Sentences | ✅ |
| M3 | Curate in Browser | ✅ — Flask API + Svelte SPA + Playwright E2E |
| M4 | Translate & Understand | ✅ — CC-CEDICT, Google Translate, SUBTLEX-CH, pinyin |
| M5 | Export to Anki | ✅ — AnkiConnect, config-driven templates, force-update |
| M6 | Stash & Screenshots | ✅ — stash tab, video frame capture, screenshot in Anki cards |
| M7 | Polish & Edit | ✅ — inline editing, settings page, theme toggle, error handling |
| M8 | Docker Deployment | ✅ — multi-stage image, docker-compose, one-command startup |
| M9 | Vocabulary Depth | ✅ — word highlighting, vocab page, cascading reclassification, Playwright E2E |
| M10 | Reading Mode | ✅ — full transcript view, keyboard shortcuts, word popups |
| M11 | Cloze Export | ✅ — cloze deletion Anki cards with screenshot hints |
| M12 | Image Search | ✅ — image search for visual context on cards |
| M13 | Difficulty Preview | ✅ — pre-mine difficulty check for a video |
| M14 | Ruby Annotations | ✅ — tone-colored pinyin ruby text above characters |
| M15 | Multi-Language Support | ✅ — data isolation, language selector, per-language Anki templates |
| M16 | Event Timeline | ✅ — append-only event log, 11 event types, created_at/updated_at timestamps |
| M17 | Ignore Word Status | ✅ — 🚫 mark words as ignored, auto-reclassify stash, 200 pytest + 42 E2E |
| M18 | Proper Name Brackets | ✅ — [square brackets] on proper names, jieba POS detection, dismissable |
| M19 | Client-Side Curation | ✅ — Svelte hashmaps for instant word highlighting, derived curatedSentences store |
| M20 | Manual Proper Names | ✅ — 👤 Mark as proper name / ❌ dismiss, guard against re-detection |
| M21 | HSK Bootstrap | ✅ — pre-mark HSK words as known from proficiency data |
| M22 | Add Sentences | ✅ — reclassify & paginate all sentences, \"Add more sentences\" button |
| M23 | Word Splitting | ✅ — edit `text_segmented` inline with spaces as word boundaries |
| M24 | Sentence Joining | ✅ — ⬆️ Merge with previous sentence, concatenates text/reading/translation |
| M25 | Subtitle Discovery | ✅ — Subtitle chip on URL paste (✅ manual / ⚠️ auto / ❌ none), richer mine errors |
| M26 | Language Selection | ✅ — Pick subtitle language, kind-aware merge gaps (300ms manual, 700ms auto), 🤖/✍️ badges |

### v1.7.2

| Feature | Description |
|---------|-------------|
| Subtitle language threading (#30) | ✅ — User-selected subtitle language code now reaches yt-dlp download, fixing manual subs that use a different language variant than config default |
| Enriched mine errors (#30) | ✅ — Frontend now shows backend's detailed error message (e.g. "This video has subtitles (Chinese manual) but download failed") instead of generic fallback |

### v1.7.1

| Feature | Description |
|---------|-------------|
| Optgroup subtitle dropdown (#29) | ✅ — Manual subs sorted A–Z at top, divider, auto captions A–Z below; users can select auto subs directly |
| Regex fix for manual subs (#29) | ✅ — yt-dlp manual section uses single-space format separator, parser now handles both spacing variants |
| Stale locator fix (#29) | ✅ — Explicit `toBeVisible()` wait before clicking `.segmented-text` on CI runners |

### v1.7.0

| Feature | Description |
|---------|-------------|
| Subtitle Discovery (M25) | ✅ — Subtitle chip on URL paste (✅ manual / ⚠️ auto / ❌ none), richer mine errors |
| Language Selection (M26) | ✅ — Pick subtitle language, kind-aware merge gaps (300ms manual, 700ms auto), 🤖/✍️ badges |
| E2E coverage (#27) | ✅ — 6 new E2E tests covering manual/auto/no-subtitle chips, language dropdown, mine flow, badges |
| Subtitle kind fix (#27) | ✅ — Section-aware yt-dlp parsing, auto-translated tracks correctly labeled auto, UI filters to manual only |

### v1.6.1

| Fix | Description |
|-----|-------------|
| SSE error display (#23) | ✅ — `MineError(stage)` wraps pipeline phases, structured SSE errors, friendly UI messages per stage, screenshot path logging, missing-image console logging |

> **Current:** M0–M26 shipped. 243 pytest + 57 E2E all green.  
> **Up next:** Stats dashboard — vocabulary growth charts, per-video breakdown, daily mining volume.

---

## License

MIT
