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

# Linting and Formatting
ruff check .           # Check for lint issues
ruff check --fix .     # Fix auto-fixable issues
ruff format .          # Format code

# Pre-commit Hooks
pre-commit install     # Install hooks
pre-commit run --all   # Run all checks manually

# Domain-only tests (no ffmpeg/network — always pass)
pytest tests/ -v --ignore=tests/test_audio.py --ignore=tests/test_pipeline.py

# Architecture tests (AST-based, 0.4s)
pytest tests/test_architecture.py -v

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

Verify: `grep -rn "^\s*(from.*adapters\|import.*adapters\|from langmine.languages\|import langmine.languages\|from langmine.web\|import langmine.web)" src/langmine/domain/` must produce zero results.

### Dependency Graph

```
app.py → domain ports + adapters               (wiring — cross-cutting ports)
app.py → language_factory → languages/          (language-specific ports)
web/routes.py → domain ports                    (API uses ports via app.config)
adapters/ → domain ports                        (implements ports)
languages/<lang>/ → domain ports                (implements LanguageProcessor)
```

Forbidden edges (enforced by CI):
- `domain/` → `adapters/`, `languages/`, `web/`  (domain is pure)
- `web/` → `adapters/` (except `app.py`), `languages/`  (use ports + factory)
- `languages/` → `adapters/`, `web/`, other language packages  (self-contained)
- `adapter → adapter`  (each adapter stands alone)
- Top-level leaf modules (`pipeline.py`, `config.py`, `db.py`, `transcript.py`, `transcript_parser.py`, `audio.py`) → `adapters/`
- Only `language_factory.py` may import from `languages/`

### Key Files

| File | Role |
|------|------|
| `src/langmine/domain/ports.py` | All abstract interfaces (`Persistence`, `LanguageProcessor`, `TranscriptSource`, `AudioProcessor`, `Translator`, `Dictionary`, `FrequencySource`, `AnkiExporter`, `ImageSearch`) |
| `src/langmine/domain/models.py` | Pure dataclasses (`Video`, `Sentence`, `VocabWord`, `Event`) + `frequency_tier()` / `frequency_badge()` |
| `src/langmine/domain/classifier.py` | `SentenceClassifier` — the i+1 engine, pure logic on ports |
| `src/langmine/language_factory.py` | **Only module allowed to import from `languages/`**. Match/case dispatch to language services. Also `get_anki_templates()`, `get_language_manifest()`, `get_available_languages()`. |
| `src/langmine/web/server.py` | Entry point (`main()`). Parses CLI args, calls `create_production_app()`, starts Flask. |
| `src/langmine/web/app.py` | `create_app()` injectable factory + `create_production_app()` wires all real adapters. **Only file in `web/` allowed to import adapters.** Also resolves `Translator` from config (Google Translate / DeepL). |
| `src/langmine/web/routes.py` | All REST endpoints. Accesses ports via `current_app.config["LANGMINE_PERSISTENCE"]` etc. |
| `src/langmine/pipeline.py` | `process_video()` — full mining pipeline (transcript → classify → enrich → screenshots → persist) |
| `src/langmine/config.py` | `Config` dataclass + `load_config()`/`save_config()` from `~/.langmine/config.yaml` |

### Port Wiring

`app.py:create_production_app()` wires concrete adapters, `create_app()` injects them into Flask config, `routes.py` retrieves them. The pattern:

```python
# app.py — wiring + injection
config = load_config()
translator = _create_translator(config)          # cross-cutting port (config-driven)
persistence = SQLitePersistence()
processor = create_language_processor(config, translator=translator)
app = create_app(persistence, processor, ...)    # injects into app.config

# routes.py — retrieval
persistence = current_app.config["LANGMINE_PERSISTENCE"]
```

Cross-cutting ports (`Translator`, `Persistence`, `TranscriptSource`, `AudioProcessor`, `AnkiExporter`, `ImageSearch`) are wired in `app.py`. Language-specific ports (`Dictionary`, `FrequencySource`) are wired in `language_factory.py`.

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

CI runs both bash grep checks (fast gate) and AST-based Python tests (precise, no false positives). Run them locally before committing:

```bash
# Fast bash checks (anchored — won't match docstrings)
```
# --- 1. domain/ is pure ---
! grep -rn "^\s*(from.*adapters\|import.*adapters)" src/langmine/domain/
! grep -rn "sqlite3\|subprocess\|requests\|urllib" src/langmine/domain/
! grep -rn "^\s*(from langmine.languages\|import langmine.languages)" src/langmine/domain/

# --- 2. web/ uses ports, not adapters/languages ---
! grep -rn "^\s*(from langmine.languages\|import langmine.languages)" src/langmine/web/
# Only app.py may import adapters:
WEB_ADAPTER_IMPORTS=$(grep -rl "^\s*from langmine.adapters" src/langmine/web/ || true)
for f in $WEB_ADAPTER_IMPORTS; do case "$f" in */app.py) ;; *) echo "FAIL: $f" ;; esac; done

# --- 3. Only language_factory.py imports from languages/ ---
LANG_IMPORTERS=$(grep -rl "^\s*(from langmine.languages\|import langmine.languages)" src/langmine/ --include="*.py" || true)
for f in $LANG_IMPORTERS; do case "$f" in */language_factory.py|*/languages/*) ;; *) echo "FAIL: $f" ;; esac; done

# --- 4. languages/ is self-contained ---
! grep -rn "^\s*(from langmine.web\|import langmine.web)" src/langmine/languages/
! grep -rn "^\s*(from langmine.adapters\|import langmine.adapters)" src/langmine/languages/
# No cross-language imports (check each languages/<lang>/ only imports its own dir)

# --- 5. adapters are independent ---
for f in src/langmine/adapters/*.py; do
  case "$(basename "$f")" in __init__.py) continue ;; esac
  grep -q "^\s*from langmine.adapters" "$f" && echo "FAIL: $f imports another adapter"
done

# --- 6. Leaf modules are adapter-free ---
for f in src/langmine/pipeline.py src/langmine/config.py src/langmine/db.py \
         src/langmine/transcript.py src/langmine/transcript_parser.py src/langmine/audio.py; do
  grep -q "^\s*(from langmine.adapters\|import langmine.adapters)" "$f" 2>/dev/null && echo "FAIL: $f"
done
```

Or run the AST-based tests for precise, false-positive-free results:

```bash
pytest tests/test_architecture.py -v   # 11 architecture rules, ~0.4s
```

## Conventions

- **Commit per milestone** — each commit is a working vertical slice.
- **TDD** — red → green → refactor. No production code without a failing test first.
- **Version source of truth** — `pyproject.toml` version field. Imported via `importlib.metadata.version("langmine")`.
- **Config** — stored at `~/.langmine/config.yaml`. Created with defaults on first run. Templates live in `languages/<lang>/anki/`, NOT in config.
- **Python 3.11+**, **Node 26+**.
