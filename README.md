# LangMine

YouTube sentence mining for language learning. Extract sentences with audio from YouTube videos, filter by vocabulary level (i+1), curate in a browser, and export to Anki flashcards.

**Status:** M3 complete — Flask API + Svelte curation UI working.

---

## Requirements

- **Python 3.11+**
- **ffmpeg** — for audio processing and clipping
- **Node.js 20+** — for building the Svelte frontend

### Installing ffmpeg

| OS | Command |
|----|---------|
| macOS | `brew install ffmpeg` |
| Ubuntu/Debian | `sudo apt install ffmpeg` |
| Windows | `winget install ffmpeg` or [ffmpeg.org](https://ffmpeg.org/download.html) |

---

## Installation

```bash
git clone https://github.com/<user>/langmine.git
cd langmine
pip install -e ".[dev]"
```

This installs LangMine in editable mode with all Python dependencies:
`yt-dlp`, `youtube-transcript-api`, `jieba`, `pypinyin`, `flask`, `pyyaml`, `pytest`, `pytest-cov`

After installation, the `langmine` command is available in your terminal.

---

## Usage

### Mine a video (CLI)

```bash
langmine mine "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

### Start the web UI

```bash
# Build the Svelte frontend (one-time, or after UI changes)
cd src/langmine/web/frontend && npm install && npm run build && cd -

# Start the server
langmine serve                  # → http://127.0.0.1:8080
langmine serve --port 9000      # custom port
```

### View help

```bash
langmine --help
langmine mine --help
langmine serve --help
```

---

## Configuration

On first run, LangMine creates `~/.langmine/config.yaml`:

```yaml
anki:
  anki_connect_url: "http://localhost:8765"
  deck_name: "Chinese::Sentence Mining"
  note_type: "LangMine Sentence"

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
```

---

## How It Works

```
YouTube URL → transcript → merge subtitle chunks into sentences
             → download full audio → clip per-sentence with padding
             → Chinese NLP (segmentation, pinyin, dictionary, translation)
             → i+1 filter (one unknown word = learnable)
             → curate in browser (keep/delete/edit)
             → export to Anki with audio + screenshots
```

---

## Architecture

Hexagonal (ports & adapters). Domain logic depends on abstract ports — never on YouTube, ffmpeg, or SQLite directly. Swap adapters without touching domain code.

```
src/langmine/
├── domain/
│   ├── ports.py          # Abstract interfaces (Persistence, Translator, etc.)
│   ├── models.py         # Pure dataclasses (Video, Sentence, VocabWord)
│   ├── classifier.py     # i+1 classification engine
│   └── services/
│       └── chinese.py    # Chinese NLP (segment, pinyin, frequency)
├── adapters/
│   ├── sqlite_persistence.py   # SQLite behind Persistence port
│   ├── youtube_transcript.py   # YouTube behind TranscriptSource port
│   └── ytdlp_audio.py          # yt-dlp+ffmpeg behind AudioProcessor port
├── web/
│   ├── app.py            # Flask app factory (port injection)
│   ├── routes.py         # REST API endpoints
│   ├── static/           # Built Svelte output (served by Flask)
│   └── frontend/         # Svelte 5 + Vite source
│       └── src/lib/      # Components: Sidebar, CardList, SentenceCard
├── pipeline.py           # End-to-end mining (accepts ports)
├── cli.py                # CLI entry point (mine, serve)
└── config.py             # YAML config with defaults
```

The cardinal rule: `domain/` never imports from `adapters/` or `web/`.

---

## Milestones

| # | Milestone | Status |
|---|-----------|--------|
| M0 | Project Scaffold | ✅ |
| M1 | Mine One Sentence | ✅ |
| M2 | Classify All Sentences | ✅ |
| M3 | Curate in Browser | ✅ — Flask API + Svelte SPA + Playwright E2E |
| M4 | Translate & Understand | ⬜ |
| M5 | Export to Anki | ⬜ |
| M6 | Stash & Screenshots | ⬜ |
| M7 | Polish & Edit | ⬜ |

---

## License

MIT
