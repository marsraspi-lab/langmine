# Contributing to LangMine

## Quick Start

```bash
git clone https://github.com/marsraspi-lab/langmine.git
cd langmine

# Python backend
pip install -e ".[dev]"

# Frontend
cd src/langmine/web/frontend
npm install
npm run build    # build once, or `npm run dev` for hot-reload dev server
cd -
```

Verify everything works:

```bash
# Python tests (no network/ffmpeg needed for domain + API tests)
pytest tests/ --ignore=tests/test_audio.py --ignore=tests/test_pipeline.py -v

# Playwright E2E tests (starts test server + headless browser)
cd src/langmine/web/frontend && npx playwright test
```

---

## Development Workflow

### Backend (Python)

Run the API server:

```bash
langmine serve
# → http://127.0.0.1:8080
```

Export to Anki (requires Anki running with AnkiConnect addon):

```bash
langmine export --all-kept
langmine export --all-kept --force-update-model  # push template changes
```

Run tests:

```bash
pytest tests/test_web_api.py -v     # API tests with fake ports
pytest tests/test_classifier.py -v  # Domain logic tests
pytest tests/adapters/ -v           # Adapter tests (db, anki, subtlex)
pytest tests/ -v                    # Full suite (needs ffmpeg for audio tests)
```

### Frontend (Svelte)

Dev server with hot reload (proxies `/api` to Flask on `:8080`):

```bash
# Terminal 1: Flask
langmine serve

# Terminal 2: Svelte dev server
cd src/langmine/web/frontend
npm run dev
# → http://localhost:5173 (proxies /api → :8080)
```

Build for production:

```bash
cd src/langmine/web/frontend && npm run build
# output goes to ../static/ — Flask serves it
```

### E2E Tests (Playwright)

```bash
cd src/langmine/web/frontend
npx playwright test              # headless
npx playwright test --ui         # interactive UI mode
npx playwright test --debug      # step-through debugger
```

The Playwright config auto-starts a Flask test server on `:8099` with fake adapters — no YouTube, ffmpeg, or SQLite needed.

---

## Architecture

LangMine uses **hexagonal architecture** (ports & adapters).

### The Cardinal Rule

```
domain/ NEVER imports from adapters/ or web/
```

Verify:

```bash
# Must produce ZERO results:
grep -r "from langmine.adapters\|from langmine.web" src/langmine/domain/
```

### Dependency Graph

```
Allowed:
  cli → domain ports + adapters        (wiring)
  web → domain ports                   (API uses ports)
  adapters → domain ports              (implements ports)
  adapters → external libs             (subprocess, sqlite3, requests)

Forbidden:
  domain → adapters        ← THE CARDINAL SIN
  domain → external libs
  adapter → adapter
```

### Ports (abstract interfaces in `domain/ports.py`)

| Port | Adapters | What it abstracts |
|------|----------|------------------|
| `Persistence` | `SQLitePersistence` | Database — store videos, sentences, vocab |
| `LanguageProcessor` | `ChineseLanguageService` | NLP — segment, pinyin, dictionary, frequency |
| `TranscriptSource` | `YouTubeTranscriptAdapter` | Subtitles — fetch from YouTube |
| `AudioProcessor` | `YtdlpAudioAdapter` | Audio — download MP3, clip sentences |
| `Translator` | `GoogleTranslateAdapter` | Sentence translation (zh→de via deep-translator) |
| `Dictionary` | `CcCedictAdapter` | Word lookup (CC-CEDICT, 125K entries) |
| `FrequencySource` | `SubtlexChAdapter` | Word frequency (SUBTLEX-CH film corpus, 99K entries) |
| `AnkiExporter` | `AnkiConnectAdapter` | Flashcard export (AnkiConnect JSON-RPC) |

### Testing with Fake Ports

Every port has a fake implementation for domain tests — zero I/O, zero network, zero ffmpeg:

```python
# test_classifier.py
persistence = FakePersistence(known_words={"我们", "学习"})
processor = FakeLanguageProcessor()
classifier = SentenceClassifier(processor, persistence)
# ... test i+1 logic without touching YouTube, ffmpeg, or SQLite
```

The same fakes power the Playwright E2E test server (`e2e/test_server.py`).

Adapter tests use real dependencies with mocked HTTP (AnkiConnect, Google Translate) or real data files (CC-CEDICT, SUBTLEX-CH).

---

## Testing Philosophy

**Strict TDD** — Red → Green → Refactor. No production code without a failing test first.

| Layer | Tool | What it tests |
|-------|------|--------------|
| Domain logic | pytest + fake ports | Classifier, pipeline, NLP — no I/O |
| API routes | pytest + Flask test client + fake ports | REST endpoints, status codes, JSON shapes |
| Adapters | pytest + mocked HTTP / real data | AnkiConnect, Translate, Dictionary, Frequency |
| Adapters (I/O) | pytest + real deps | SQLite, yt-dlp, ffmpeg integration |
| E2E UI | Playwright + fake server | Svelte components, button clicks, state changes |

---

## Svelte Component Tree

```
App.svelte
├── Sidebar.svelte        — video list, mine form, export button
└── CardList.svelte       — filter tabs + card grid
    └── SentenceCard.svelte — text, pinyin, translation, audio, actions
```

State management via Svelte 5 stores (`src/lib/stores.js`):
- `videos`, `sentences` — writable stores
- `selectedVideoId`, `currentFilter` — writable stores
- `selectedVideo` — derived store
- `mineStatus`, `exportStatus` — writable stores (UI feedback)
- `mining`, `exporting` — writable stores (loading states)

API calls via `src/lib/api.js` — thin wrappers around `fetch()`.

---

## Project Conventions

- **Commit per milestone.** Each commit is a working vertical slice.
- **Architecture review after each milestone.**
- **Python formatting:** follow PEP 8.
- **Svelte:** Svelte 5 with runes (`$props()`, `$state()`). Scoped CSS per component.
- **No build step for Python.** `pip install -e .` in editable mode.
- **Frontend build step required.** `npm run build` before `langmine serve`.
- **Test isolation.** Domain tests use fakes; adapter tests mock external HTTP or use local data files. Audio tests require ffmpeg on the host machine.
