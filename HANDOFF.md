# Handoff — 2026-05-31 (Multi-Language Data Isolation + Anki Template Extraction)

## Where We Are

**Multi-language support complete.** Ready for review/merge into `main`.

- **`main`:** v1.1.0 tag (`6f80bdd`) — M0–M14 + decouple Chinese. 217 pytest + 42 E2E.
- **Working tree:** 200 pytest pass. All changes uncommitted.
- **Status:** v1.2.0 material — multi-language data isolation, `/api/languages` endpoint, frontend language selector, Anki templates as files in language extension.

## What Changed

### Data Isolation
- `language_code TEXT NOT NULL DEFAULT 'zh'` column added to `videos`, `sentences`, `vocab` tables (DB schema v2).
- `Sentence`, `Video`, `VocabWord` models have `language_code: str` field.
- `SQLitePersistence` filters all SELECTs by `language_code`; INSERTs include it.
- `_get_language_code()` helper in `routes.py` reads `config.source_language`.
- **No migration needed** — delete `~/.langmine/langmine.db` to recreate with new schema (no production users).

### New API Endpoint
- `GET /api/languages` — returns `{"languages": [{"code": "zh", "name": "中文"}]}`.
- Factory function `get_available_languages()` drives it.

### Frontend Language Selector
- `<select>` dropdown in `App.svelte` top bar — shows available languages from `/api/languages`.
- On change: `PUT /api/config` with `source_language`, then reloads videos and sentences.
- New stores: `languages` (writable), `currentLanguage` (writable).
- New actions: `loadLanguages()`, `selectLanguage(code)`.

### Anki Templates Moved to Language Extension
- Card templates extracted from `config.yaml` / `Config` class → files under `languages/chinese/anki/`:
  - `basic/{front.html, back.html, css.css}`
  - `cloze/{front.html, back.html, css.css}`
- Language manifest (`languages/chinese/__init__.py`) declares `MANIFEST` with `name`, `deck_name`, `note_type`, `cloze_note_type`.
- Factory functions: `get_anki_templates(lang)` and `get_language_manifest(lang)`.
- `POST /api/export/anki` now reads templates from factory instead of config.

### Config Surface Cleaned
- `GET /api/config` no longer returns `deck_name` or `note_type`.
- `PUT /api/config` `ALLOWED` set no longer accepts template fields (`cloze_note_type`, `cloze_card_css`, etc.).
- SettingsPage (Svelte) removed Deck Name / Note Type inputs.

### Tests
- `tests/test_multi_language.py` — 5 tests: `language_code` on models + isolation.
- `tests/test_web_api.py::TestLanguagesEndpoint` — 2 tests for `/api/languages`.
- `tests/test_config.py::TestConfigApiAllowed` — no longer expects cloze fields in ALLOWED.
- All FakePersistence classes in tests accept `language_code` kwargs.

## Architecture Rules (unchanged)

- Hexagonal: `domain/` never imports from `adapters/` or `web/`
- `domain/` never imports from `languages/`
- `web/` never imports from `languages/`
- Language packages never cross-import each other
- Language packages never import from `web/`
- Only `language_factory.py` imports from `languages/` — THE single switch point
- `routes.py` must not import from `adapters/` (wire through Flask config)
- TDD: failing test first, then implementation

## Key File Structure (current)

```
src/langmine/
├── domain/              # Language-agnostic core
├── adapters/            # Language-agnostic adapters only
├── languages/
│   └── chinese/
│       ├── __init__.py         # MANIFEST + get_anki_templates() + exports
│       ├── service.py          # ChineseLanguageService
│       ├── dictionary.py       # CcCedictAdapter
│       ├── frequency.py        # SubtlexChAdapter + JiebaFrequencyAdapter
│       ├── hsk_data.py         # HSK proficiency data
│       ├── anki/               # Card templates as files
│       │   ├── basic/{front.html, back.html, css.css}
│       │   └── cloze/{front.html, back.html, css.css}
│       └── data/               # CC-CEDICT + SUBTLEX corpus
├── language_factory.py  # Factory: processors, templates, manifest, proficiency
├── web/                 # No language-specific code
├── pipeline.py          # Accepts ports, stamps language_code
├── cli.py               # Uses factory
└── config.py
tests/
├── test_multi_language.py      # 5 tests — model + isolation
├── test_language_factory.py
├── languages/chinese/          # 4 test files
└── ...
```

## Key Commands

```bash
# Run all tests
cd /root/projects/langmine
python -m pytest tests/ -q

# Run E2E tests
cd src/langmine/web/frontend
npx playwright test

# Build frontend
cd src/langmine/web/frontend && npm run build

# Verify architecture isolation
grep -r "from langmine.languages" src/langmine/domain/      # must be EMPTY
grep -r "from langmine.languages" src/langmine/web/         # must be EMPTY
grep -r "from langmine.adapters" src/langmine/domain/       # must be EMPTY

# Docker build with version
docker build --build-arg VERSION=1.2.0 -t langmine:1.2.0 .
```

## Version Infrastructure

Single source of truth: `pyproject.toml` → `importlib.metadata.version("langmine")`.

| Channel | How |
|---|---|
| CLI | `langmine --version` |
| API | `GET /api/version` → `{"version": "1.2.0", "name": "langmine"}` |
| UI | Settings page footer (fetches `/api/version` on mount) |
| Docker | `--build-arg VERSION=1.2.0` → OCI label |

## Multi-Language Plan

See `.hermes/plans/2026-05-30-decouple-chinese.md` for full phase breakdown (7 phases, ~35 tasks). Spanish, Korean, Russian are planned — create `languages/<code>/` with service + dictionary + frequency + anki templates + manifest, add to factory.
