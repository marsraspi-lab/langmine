# Handoff — 2026-05-31 (Proper Name Brackets)

## Where We Are

**Proper name brackets complete.** Merged to `main` (PR #13).

- **`main`:** v1.5.0 — M0–M18 (proper name brackets). 206 pytest + 42 E2E.
- **What's new:** `LanguageProcessor.is_proper_name()` port method. Chinese implementation using jieba posseg (detects person names `nr`, place names `ns`). Transcript API and preview endpoint assign `status="proper-name"` — excluded from i+1 unknown counting. Frontend renders `[brackets]` via CSS `::before`/`::after`. "Not a proper name" popover action dismisses via `PATCH /api/vocab/{word}` with `{proper_name: false}`.
- **Status:** v1.5.0 material — all 18 milestones complete.

## What Changed (M18)

### New Port Method
- `LanguageProcessor.is_proper_name(token) -> bool` — detected via jieba posseg in Chinese
- Proper name POS tags: `nr` (person), `ns` (place), `nrfg` (given name), `nrt` (transliterated)

### Transcript & Preview
- `_words_array()` checks `is_proper_name()` and assigns `status="proper-name"`
- Preview endpoint token classification includes proper-name check
- Proper names excluded from i+1 unknown counting (like non-words)
- Known/ignored words take priority over proper-name detection

### New API Behavior
- `PATCH /api/vocab/{word}` accepts `{"proper_name": false}` → marks word as `learning`
- Logs `dismissed_proper_name` event

### Frontend
- CSS `::before`/`::after` brackets on `.word-proper-name` (faded gray)
- "❌ Not a proper name" button in word popover (visible when status is proper-name)
- `dismissProperName()` in `api.js`

### Infrastructure
- `sandbox/Dockerfile`: `libasound2` → `libasound2t64` (Debian trixie rename)
- `pyproject.toml` bumped to 1.5.0

### Tests
- `tests/languages/chinese/test_service.py` — 4 tests: person/place detection, common word/particle rejection
- `tests/test_web_transcript.py::TestProperNameInTranscript` — 1 test: transcript proper-name status
- `tests/test_web_api.py::TestDismissProperName` — 1 test: dismiss API flow

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
