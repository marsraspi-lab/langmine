# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Commands

```bash
# Python backend (use .venv!)
source .venv/bin/activate
pip install -e ".[dev]"

# Frontend
cd src/langmine/web/frontend && npm install && npm run build && cd -

# Full test suite (needs ffmpeg for audio tests)
pytest tests/ -v

# Domain-only tests (no ffmpeg/network — always pass)
pytest tests/ -v --ignore=tests/test_audio.py --ignore=tests/test_pipeline.py

# Single test file
pytest tests/test_web_api.py -v

# E2E tests (Playwright)
cd src/langmine/web/frontend && npx playwright test

# Run the app
langmine                           # → http://127.0.0.1:8080
langmine --port 9000               # custom port

# Dev with hot reload (two terminals):
# Terminal 1: langmine
# Terminal 2: cd src/langmine/web/frontend && npm run dev   # → :5173 proxies /api → :8080
```

## Architecture: Hexagonal (Ports & Adapters)

### Cardinal Rule

```
domain/ NEVER imports from adapters/, web/, or languages/
```

Verify: `grep -r "from langmine.adapters\|from langmine.web\|from langmine.languages" src/langmine/domain/` must produce zero results.

### Dependency Graph

```
server.py → domain ports + adapters          (wiring)
server.py → language_factory → languages/    (single switch point)
web/app.py, web/routes.py → domain ports     (API uses ports)
adapters/ → domain ports                     (implements ports)
languages/<lang>/ → domain ports             (implements LanguageProcessor)
```

Also forbidden: `web/` → `languages/` (must go through factory), `adapter → adapter`, cross-language imports, `languages/` → `web/`.

### Key Files

| File | Role |
|------|------|
| `src/langmine/domain/ports.py` | All abstract interfaces (`Persistence`, `LanguageProcessor`, `TranscriptSource`, `AudioProcessor`, `Translator`, `Dictionary`, `FrequencySource`, `AnkiExporter`, `ImageSearch`) |
| `src/langmine/domain/models.py` | Pure dataclasses (`Video`, `Sentence`, `VocabWord`, `Event`) + `frequency_tier()` / `frequency_badge()` |
| `src/langmine/domain/classifier.py` | `SentenceClassifier` — the i+1 engine, pure logic on ports |
| `src/langmine/language_factory.py` | **Only module allowed to import from `languages/`**. Match/case dispatch to language services. Also `get_anki_templates()`, `get_language_manifest()`, `get_available_languages()`. |
| `src/langmine/web/server.py` | Entry point (`main()`). Wires real adapters, starts Flask. |
| `src/langmine/web/app.py` | `create_app()` factory — injects ports into `app.config` as `LANGMINE_*` keys. Serves Svelte static files. |
| `src/langmine/web/routes.py` | All REST endpoints. Accesses ports via `current_app.config["LANGMINE_PERSISTENCE"]` etc. |
| `src/langmine/pipeline.py` | `process_video()` — full mining pipeline (transcript → classify → enrich → screenshots → persist) |
| `src/langmine/config.py` | `Config` dataclass + `load_config()`/`save_config()` from `~/.langmine/config.yaml` |

### Port Wiring

`server.py` wires concrete adapters, `app.py` injects them into Flask config, `routes.py` retrieves them. The pattern:

```python
# server.py — wiring
persistence = SQLitePersistence(db_path)
language = create_language_processor(config)
app = create_app(persistence, language, ...)

# app.py — injection
app.config["LANGMINE_PERSISTENCE"] = persistence

# routes.py — retrieval
persistence = current_app.config["LANGMINE_PERSISTENCE"]
```

### Adding a Language

Create `languages/<code>/` with: `__init__.py` (containing `MANIFEST` dict + `get_anki_templates()`), `service.py`, `dictionary.py`, `frequency.py`, and `anki/{basic,cloze}/` template directories. Add `case "<code>"` to all match/case blocks in `language_factory.py` and add to the `LANGUAGES` list. No changes to `domain/`, `web/`, or `adapters/` needed.

## Testing Patterns

### Fake Ports

Every port has a fake implementation used in tests — zero I/O, zero network. Fakes live inline in test files (not a shared module). The same fake patterns power both pytest and the Playwright E2E test server (`e2e/test_server.py`).

```python
# Pattern for API tests
class FakePersistence:
    def __init__(self, **kwargs): ...

def client(persistence, processor, transcript, audio):
    app = create_app(persistence, processor, transcript, audio)
    return app.test_client()

def test_something(client):
    resp = client.get("/api/endpoint")
    assert resp.status_code == 200
```

### Test Layer Map

| Layer | Tool | What |
|-------|------|------|
| Domain logic | pytest + fake ports | Classifier, pipeline — no I/O |
| API routes | pytest + Flask test client + fake ports | REST endpoints, status codes, JSON shapes |
| Adapters | pytest + mocked HTTP / real data files | AnkiConnect, Translate, Dictionary |
| Audio/yt-dlp | pytest + real deps (needs ffmpeg) | Integration tests |
| E2E UI | Playwright + fake server on :8099 | Svelte components, clicks, state |

## Frontend (Svelte 5)

- **Svelte 5 runes only** — `$state()`, `$effect()`, `$props()`. No Svelte 4 stores (`writable`, `$:`).
- **Single state object** in `src/lib/stores.svelte.js` — `app` holds all reactive state (videos, sentences, knownWords Set, theme, toasts, etc.). Direct property assignment, no `.set()`/`.update()`.
- **Client-side curation** — `curatedSentences()` derived value computes i+1/i0/stashed status from `knownWords`/`learningWords`/`ignoredWords` Sets. Server is source-of-truth for vocab only.
- **Build output** goes to `../static/` (served by Flask). Dev server on `:5173` proxies `/api` to Flask on `:8080`.
- **E2E test server** (`e2e/test_server.py`) auto-starts via Playwright config on port 8099 with all fake ports.

## Pre-Commit Checks

CI runs these architecture checks. Run them locally before committing:

```bash
# No domain→adapter imports
! grep -r "from.*adapters\|import.*adapters" src/langmine/domain/

# No domain external I/O
! grep -r "sqlite3\|subprocess\|requests\|urllib" src/langmine/domain/

# No domain→languages imports
! grep -r "from langmine.languages\|import langmine.languages" src/langmine/domain/

# No web→languages imports
! grep -r "from langmine.languages\|import langmine.languages" src/langmine/web/

# No cross-language imports
# (check each languages/<lang>/ only imports from its own directory)

# No languages→web imports
! grep -r "from langmine.web\|import langmine.web" src/langmine/languages/

# Only app.py imports adapters in web layer
WEB_ADAPTER_IMPORTS=$(grep -rl "from langmine.adapters" src/langmine/web/ || true)
# app.py is the only allowed file
```

## Conventions

- **Commit per milestone** — each commit is a working vertical slice.
- **TDD** — red → green → refactor. No production code without a failing test first.
- **Version source of truth** — `pyproject.toml` version field. Imported via `importlib.metadata.version("langmine")`.
- **Config** — stored at `~/.langmine/config.yaml`. Created with defaults on first run. Templates live in `languages/<lang>/anki/`, NOT in config.
- **Python 3.11+**, **Node 26+**.
