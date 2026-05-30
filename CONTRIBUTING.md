# Contributing to LangMine

## Quick Start

```bash
git clone https://github.com/marsraspi-lab/langmine.git
cd langmine

# ffmpeg (one-time, survives if using system install)
./scripts/setup-ffmpeg.sh

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
# Full Python test suite
pytest tests/ -v

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
| `LanguageProcessor` | Factory + `languages/*/service.py` | NLP — segment, reading, dictionary, frequency |
| `TranscriptSource` | `YouTubeTranscriptAdapter` | Subtitles — fetch from YouTube |
| `AudioProcessor` | `YtdlpAudioAdapter` | Audio — download MP3, clip sentences, capture frames |
| `Translator` | `GoogleTranslateAdapter` | Sentence translation (via deep-translator) |
| `Dictionary` | `languages/*/dictionary.py` (e.g. CC-CEDICT) | Word lookup |
| `FrequencySource` | `languages/*/frequency.py` (e.g. SUBTLEX-CH) | Word frequency |
| `AnkiExporter` | `AnkiConnectAdapter` | Flashcard export (AnkiConnect JSON-RPC) |

**Adding a language:** Create `languages/<code>/` with 4 files: `__init__.py`, `service.py`, `dictionary.py`, `frequency.py`. Add `case "<code>"` to `language_factory.py`. No code changes needed in domain, web, or adapters.

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
├── Top bar              — brand, curation/settings/vocab nav, theme toggle
├── Sidebar.svelte       — video list, mine form, export button, preview
├── CardList.svelte      — filter tabs (All/Kept/Deleted/Stash/Read) + sentence cards
│   ├── SentenceCard.svelte — text, reading, translation, audio, annotation, actions
│   │                         (click-to-edit reading/translation/segmentation)
│   └── TranscriptView.svelte — full reading mode transcript with keyboard shortcuts
├── ImagePicker.svelte   — image search grid for cloze card hints
├── PreviewPanel.svelte  — difficulty preview stats + read-only transcript
├── VocabPage.svelte     — searchable vocabulary list with word detail panel
├── SettingsPage.svelte  — config form (Anki, NLP, mining, vocab, network)
└── Toast overlay        — success/error notifications
```

State management via Svelte 5 stores (`src/lib/stores.js`):
- `videos`, `sentences` — writable stores
- `selectedVideoId`, `currentFilter` — writable stores
- `selectedVideo` — derived store
- `mineStatus`, `exportStatus` — writable stores (UI feedback)
- `mining`, `exporting` — writable stores (loading states)
- `toasts` — writable store (notification queue)
- `config` — writable store (settings data)
- `theme` — writable store (dark/light, persisted to localStorage)
- `currentView` — writable store (curation | settings | vocab)
- `readingMode` — writable store (reading view toggle)
- `clozeMode` — writable store (cloze deletion checkbox)
- `previewResult` — writable store (difficulty preview data)
- `imageSearchActive` — writable store (image picker open state)

API calls via `src/lib/api.js` — thin wrappers around `fetch()`. Supports `GET`, `POST`, `PATCH`, and `PUT`.

---

## Project Conventions

- **Commit per milestone.** Each commit is a working vertical slice.
- **Architecture review after each milestone.**
- **Python formatting:** follow PEP 8.
- **Svelte:** Svelte 5 with runes (`$props()`, `$state()`). Scoped CSS per component.
- **No build step for Python.** `pip install -e .` in editable mode.
- **Frontend build step required.** `npm run build` before `langmine serve`.
- **Test isolation.** Domain tests use fakes; adapter tests mock external HTTP or use local data files. Audio tests use project-bundled ffmpeg binaries or system PATH fallback.
- **Frequency tiers** are pure domain logic in `domain/models.py` — adapters delegate to `frequency_tier()`/`frequency_badge()` rather than duplicating thresholds.

---

## Pre-Commit Checklist

Run through these before committing or submitting a PR.

### CI Pipeline

GitHub Actions runs automatically on every push and PR:

- **`check`** (every push, ~30s) — architecture grep, domain + adapter tests, frontend build
- **`e2e`** (PRs only, ~40s) — Playwright E2E tests with fake server

You can run the same checks locally before pushing:

```bash
# Architecture checks (same as CI "check" step)
! grep -r "from.*adapters\|import.*adapters" src/langmine/domain/
! grep -r "sqlite3\|subprocess\|requests\|urllib" src/langmine/domain/

# Fast test suite (same as CI — skips audio/pipeline)
pytest tests/ -q --ignore=tests/test_audio.py --ignore=tests/test_pipeline.py

# Frontend build
cd src/langmine/web/frontend && npm ci && npm run build && cd -

# E2E tests
cd src/langmine/web/frontend && npx playwright test && cd -
```

### ✅ Before every commit

```bash
# 1. All tests pass (Python + E2E)
pytest tests/ -q
cd src/langmine/web/frontend && npx playwright test && cd -
```

```bash
# 2. Architecture: domain never imports from adapters, web, languages, or external I/O
grep -r "from.*adapters\|import.*adapters" src/langmine/domain/    # must be EMPTY
grep -r "sqlite3\|subprocess\|requests\|urllib" src/langmine/domain/  # must be EMPTY
grep -r "from langmine.languages" src/langmine/domain/      # must be EMPTY
grep -r "from langmine.languages" src/langmine/web/         # must be EMPTY
```

```bash
# 3. Frontend builds without errors
cd src/langmine/web/frontend && npm run build && cd -
```

### ✅ Before merging a milestone

| Check | Command |
|-------|---------|
| Full test suite | `pytest tests/ -q` (all tests) |
| E2E tests | `npx playwright test` (42 tests) |
| Cardinal rule | `grep -r "from.*adapters" src/langmine/domain/` → empty |
| Domain→languages | `grep -r "from langmine.languages" src/langmine/domain/` → empty |
| Web→languages | `grep -r "from langmine.languages" src/langmine/web/` → empty |
| Language cross-imports | `grep -r "from langmine.languages" src/langmine/languages/chinese/ \| grep -v chinese` → empty |
| No adapter→adapter imports | `grep -r "from langmine.adapters" src/langmine/adapters/` → only `__init__.py` |
| Frequency tiers in domain | `grep "frequency_tier\|frequency_badge" src/langmine/domain/models.py` → found |
| Web layer uses ports | `grep -r "from langmine.adapters" src/langmine/web/` → none except wiring in `app.py` |
| Domain models are pure | `grep -r "open\|requests\|subprocess\|sqlite3" src/langmine/domain/models.py` → empty |
| Milestones in README updated | Check README milestones table |
| Commit message follows `type: subject` | `feat:`, `fix:`, `refactor:`, `test:`, `docs:` |
| No stale built assets | `git status` — `src/langmine/web/static/assets/` should have exactly 1 CSS + 1 JS |

### ✅ Architecture self-review

Before marking a milestone complete, verify:

1. **New code in `domain/`** — does it import anything from `adapters/`? If yes, fix it.
2. **New code in `web/routes.py`** — does it import a specific adapter instead of going through a port? If yes, move the logic to domain or inject the port.
3. **New adapter** — does it implement exactly one port? Does it contain business logic? If yes, move logic to domain.
4. **New port** — is it abstract? Do tests provide a fake implementation? If no, add one.
5. **Test isolation** — do domain tests pass without ffmpeg, YouTube, or SQLite? Run `pytest tests/ --ignore=tests/test_audio.py --ignore=tests/test_pipeline.py --ignore=tests/adapters/` and all must pass.
