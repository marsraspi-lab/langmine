# LangMine

YouTube sentence mining for language learning. Extract sentences with audio from YouTube videos, filter by vocabulary level (i+1), curate in a browser, and send flashcards directly to Anki via AnkiConnect.

**Status:** v1.1.0 — M0–M14 + decouple Chinese (PR #9). 217 pytest + 42 E2E. All tests pass.

---

## Requirements

- **Python 3.11+**
- **ffmpeg** — for audio processing and clipping (auto-downloaded via setup script if missing)
- **Anki** + **AnkiConnect addon** (ID: 2055492159) — for flashcard export
- **Node.js 20+** — for building the Svelte frontend

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
docker build --build-arg VERSION=1.1.0 -t langmine:1.1.0 .
docker run -p 8080:8080 -v ~/.langmine:/root/.langmine \
  --add-host=host.docker.internal:host-gateway \
  langmine:1.1.0
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
`yt-dlp`, `youtube-transcript-api`, `jieba`, `pypinyin`, `deep-translator`, `flask`, `pyyaml`, `requests`, `pytest`, `pytest-cov`

Chinese language processing uses `jieba` (segmentation), `pypinyin` (reading), and CC-CEDICT. Other languages use their own NLP toolchain — see `languages/` directory.

---

## Usage

### Mine a video (CLI)

```bash
langmine mine "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

### Start the web UI

```bash
langmine serve                  # → http://127.0.0.1:8080
langmine serve --port 9000      # custom port
```

The web UI lets you browse mined sentences, edit readings/translations/segmentation inline, keep or delete sentences, mark words as known, and configure settings.

### Export to Anki

```bash
# Export all kept sentences
langmine export --all-kept

# Export from a specific video
langmine export --video-id 1

# Force-update card templates (after editing config.yaml)
langmine export --all-kept --force-update-model
```

Or use the **📦 Export to Anki** button in the sidebar. Check "⚡ Update card templates" to push template changes from `config.yaml`.

Anki must be running with the AnkiConnect addon installed.

### View help and version

```bash
langmine --help
langmine --version                  # e.g. "langmine 1.1.0"
langmine mine --help
langmine serve --help
langmine export --help
```

---

## Configuration

On first run, LangMine creates `~/.langmine/config.yaml`. All values can also be edited from the **⚙️ Settings** page in the web UI.

```yaml
anki:
  anki_connect_url: "http://host.docker.internal:8765"
  deck_name: "Chinese::Sentence Mining"
  note_type: "LangMine Sentence"

  # Card styling and templates (edit these to customize flashcards)
  card_css: |
    .card { font-family: Arial, sans-serif; font-size: 20px; }
    .chinese { font-size: 28px; margin: 20px 0; }
    .reading { color: #2e7d32; font-style: italic; }
    .translation { font-size: 22px; }
    .word { color: #e53935; font-size: 18px; }
    .screenshot { margin-top: 16px; }

  card_front_template: |
    <div class="chinese">{{sentence_zh}}</div>
    {{#audio}}{{audio}}{{/audio}}

  card_back_template: |
    <div class="chinese">{{sentence_zh}}</div>
    {{#audio}}{{audio}}{{/audio}}
    <hr id="answer">
    <div class="reading">{{sentence_reading}}</div>
    <div class="translation">{{translation_de}}</div>
    {{#unknown_word}}<div class="word">🆕 {{unknown_word}}</div>{{/unknown_word}}
    {{#screenshot}}<div class="screenshot">{{screenshot}}</div>{{/screenshot}}

languages:
  source: "zh"
  target: "de"

nlp:
  translation_api: "google"

mining:
  sentence_gap_ms: 500        # max gap between subtitle chunks when merging
  audio_pad_before_ms: 250    # padding before sentence audio
  audio_pad_after_ms: 300     # padding after sentence audio
  max_cards_per_video: 20     # i+1 candidates per video
  max_stash_cards: 20         # stash re-scan candidates

vocab:
  # No generic vocab config needed — language packages manage their own bootstrapping

storage:
  data_dir: "~/.langmine/data"   # audio clips, screenshots, downloads

network:
  user_agent: ""                # custom User-Agent (e.g. "Mozilla/5.0 ...")
```

See **[docs/TEMPLATES.md](docs/TEMPLATES.md)** for card template customization — available fields, Mustache conditionals, and Anki-side editing.

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
             → curate in browser (keep/delete/I-know-this, edit reading/translation/segmentation)
             → dark/light theme toggle
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
│       ├── service.py          # ChineseLanguageService (segment, reading, classify)
│       ├── dictionary.py       # CcCedictAdapter (CC-CEDICT, 125K entries)
│       ├── frequency.py        # SubtlexChAdapter + JiebaFrequencyAdapter
│       ├── hsk.py              # HSK proficiency levels
│       └── data/               # CC-CEDICT dictionary + SUBTLEX corpus
├── language_factory.py   # Single switch point for language loading
├── web/
│   ├── app.py            # Flask app factory (port injection)
│   ├── routes.py         # REST API endpoints
│   ├── static/           # Built Svelte output (served by Flask)
│   └── frontend/         # Svelte 5 + Vite source (language-agnostic)
├── pipeline.py           # End-to-end mining (accepts ports)
├── cli.py                # CLI entry point (mine, serve, export)
├── config.py             # YAML config with defaults
├── audio.py              # yt-dlp/ffmpeg helpers (uses project binaries)
└── bin/                  # Static ffmpeg/ffprobe (downloaded via setup script)
```

The cardinal rule: `domain/` never imports from `adapters/` or `web/`. Similarly, `domain/` and `web/` never import from `languages/` — only `language_factory.py` touches language packages.

### Adding a Language

Create `languages/<code>/` with 4 files:

```
languages/spanish/
├── __init__.py           # Package init
├── service.py            # SpanishLanguageService(LanguageProcessor)
├── dictionary.py         # SpanishDict adapter (Dictionary port)
└── frequency.py          # SUBTLEX-ES adapter (FrequencySource port)
```

Then add to `language_factory.py`:

```python
case "es":
    from langmine.languages.spanish import SpanishLanguageService, SpanishDict, SubtlexEsAdapter
    return SpanishLanguageService(SpanishDict(), GoogleTranslateAdapter(), SubtlexEsAdapter())
```

No changes needed in `domain/`, `web/`, `adapters/`, `pipeline.py`, or `cli.py` — the factory handles everything. The Svelte frontend is fully language-agnostic — it renders whatever JSON the API returns.

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

> **Plan:** `.hermes/plans/2026-05-29-m10-m14-reading-cloze-image-preview-ruby.md`

---

## License

MIT
