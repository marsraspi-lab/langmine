# LangMine

YouTube sentence mining for language learning. Extract sentences with audio from YouTube videos, filter by vocabulary level (i+1), curate in a browser, and send flashcards directly to Anki via AnkiConnect.

**Status:** v1.1 — M0–M8 complete. All tests pass.

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
docker build -t langmine .
docker run -p 8080:8080 -v ~/.langmine:/root/.langmine \
  --add-host=host.docker.internal:host-gateway \
  langmine
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

The web UI lets you browse mined sentences, edit pinyin/translations/segmentation inline, keep or delete sentences, mark words as known, and configure settings.

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

### View help

```bash
langmine --help
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
    .pinyin { color: #2e7d32; font-style: italic; }
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
    <div class="pinyin">{{sentence_pinyin}}</div>
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
  hsk_bootstrap: 3            # HSK levels 1-3 treated as known

storage:
  data_dir: \"~/.langmine/data\"   # audio clips, screenshots, downloads
```

See **[docs/TEMPLATES.md](docs/TEMPLATES.md)** for card template customization — available fields, Mustache conditionals, and Anki-side editing.

---

## How It Works

```
YouTube URL → transcript → merge subtitle chunks into sentences
             → download full audio → clip per-sentence with padding
             → capture screenshot at sentence midpoint
             → Chinese NLP (jieba segmentation, pypinyin, CC-CEDICT dictionary,
                Google Translate, SUBTLEX-CH frequency ranking)
             → i+1 filter (one unknown word = learnable)
             → stash i+2+ sentences for later
             → curate in browser (keep/delete/I-know-this, edit pinyin/translation/segmentation)
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
│   └── services/
│       └── chinese.py    # Chinese NLP (segment, pinyin, frequency)
├── adapters/
│   ├── sqlite_persistence.py   # SQLite behind Persistence port
│   ├── youtube_transcript.py   # YouTube behind TranscriptSource port
│   ├── ytdlp_audio.py          # yt-dlp+ffmpeg behind AudioProcessor port
│   ├── google_translate.py     # deep-translator behind Translator port
│   ├── cc_cedict.py            # CC-CEDICT behind Dictionary port
│   ├── subtlex_ch.py           # SUBTLEX-CH behind FrequencySource port
│   ├── jieba_frequency.py      # jieba dict behind FrequencySource port
│   └── anki_connect.py         # AnkiConnect behind AnkiExporter port
├── web/
│   ├── app.py            # Flask app factory (port injection)
│   ├── routes.py         # REST API endpoints
│   ├── static/           # Built Svelte output (served by Flask)
│   └── frontend/         # Svelte 5 + Vite source
│       └── src/lib/      # Components: Sidebar, CardList, SentenceCard, SettingsPage
├── data/
│   ├── cedict/           # CC-CEDICT dictionary (125K entries)
│   ├── SUBTLEX-CH-*      # Word frequency corpus
│   └── hsk/              # HSK level data (coming in M9)
├── pipeline.py           # End-to-end mining (accepts ports)
├── cli.py                # CLI entry point (mine, serve, export)
├── config.py             # YAML config with defaults
├── audio.py              # yt-dlp/ffmpeg helpers (uses project binaries)
└── bin/                  # Static ffmpeg/ffprobe (downloaded via setup script)
```

The cardinal rule: `domain/` never imports from `adapters/` or `web/`.

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

---

## License

MIT
