# LangMine

YouTube sentence mining for language learning. Extract sentences with audio clips from YouTube videos, filter by vocabulary level (i+1), curate in a browser, and export to Anki flashcards.

**Status:** In development (M1 complete — first vertical slice working)

---

## Requirements

- **Python 3.11+**
- **ffmpeg** — for audio processing and clipping
- **yt-dlp** — for YouTube audio download (installed automatically)

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

This installs LangMine in editable mode along with all dependencies:
`yt-dlp`, `youtube-transcript-api`, `jieba`, `pypinyin`, `flask`, `pyyaml`, `pytest`, `pytest-cov`

After installation, the `langmine` command is available in your terminal.

---

## Usage

### Mine a video

```bash
# Mine the first sentence from a YouTube video (demonstration)
langmine mine "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# With dry-run (no audio download, just show what would be processed)
langmine mine <url> --dry-run
```

### Start the web UI (coming in M3)

```bash
langmine serve                  # defaults to http://127.0.0.1:8080
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

On first run, LangMine creates `~/.langmine/config.yaml` with sensible defaults:

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

Edit this file to change defaults, or use the Settings page in the web UI (M7).

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

## Development

- **Plan:** [PLAN.md](PLAN.md) — architecture, decisions, milestones
- **Methodology:** Strict TDD (Red → Green → Refactor). No production code without a failing test first.

### Project Structure

```
langmine/
├── PLAN.md                # Full architecture and milestone plan
├── pyproject.toml         # Dependencies and build config
├── src/langmine/
│   ├── cli.py             # CLI entry point (mine, serve)
│   ├── config.py          # YAML config with defaults
│   ├── db.py              # SQLite schema and migrations
│   ├── processors.py      # LanguageProcessor ABC + ChineseProcessor stub
│   ├── transcript.py      # YouTube transcript fetching + sentence merging
│   ├── audio.py           # yt-dlp download + ffmpeg audio clipping
│   └── pipeline.py        # End-to-end mining pipeline
├── tests/                 # Test suite (38 tests, all passing)
└── data/                  # Bundled data (HSK, SUBTLEX-CH, CC-CEDICT)
```

### Milestones

| # | Milestone | Tests | Status |
|---|-----------|-------|--------|
| M0 | Project Scaffold | 18 | ✅ Complete |
| M1 | Mine One Sentence | 20 | ✅ Complete |
| M2 | Classify All Sentences | 22 | ✅ Complete |
| M3 | Curate in Browser | — | |
| M4 | Translate & Understand | — | |
| M5 | Export to Anki | — | |
| M6 | Stash & Screenshots | — | |
| M7 | Polish & Edit | — | |

### Running Tests

```bash
# All tests
pytest tests/ -v

# Specific module
pytest tests/test_transcript.py -v

# With coverage
pytest tests/ --cov=langmine --cov-report=term-missing
```

---

## License

MIT
