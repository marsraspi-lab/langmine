# Handoff — 2026-05-30 (Decouple Chinese, PR #9)

## Where We Are

**Decouple Chinese refactor complete.** PR #9 open against `main`, ready for review/merge.

- **`main`:** v1.0.0 tag (`5ab98e7`) — M0–M14, 213 pytest + 42 E2E
- **`refactor/decouple-chinese`:** v1.1.0 (`756ef38`) — 217 pytest + 42 E2E (adds 4 decoupling tests)
- CI passes: `check` ✅ + `e2e` ✅

## Version Infrastructure

Single source of truth: `pyproject.toml` → `importlib.metadata.version("langmine")`.

| Channel | How |
|---|---|
| CLI | `langmine --version` |
| API | `GET /api/version` → `{"version": "1.1.0", "name": "langmine"}` |
| UI | Settings page footer (fetches `/api/version` on mount) |
| Docker | `--build-arg VERSION=1.1.0` → OCI `org.opencontainers.image.version` label |

## Architecture Rules (updated)

- Hexagonal: `domain/` never imports from `adapters/` or `web/`
- **NEW:** `domain/` never imports from `languages/`
- **NEW:** `web/` never imports from `languages/`
- **NEW:** Language packages never cross-import each other
- **NEW:** Language packages never import from `web/`
- Only `language_factory.py` imports from `languages/` — it is THE single switch point
- Adding a language = `languages/<code>/` with 4 files + `case "<code>"` in factory
- `routes.py` must not import from `adapters/` (wire through Flask config)
- YouTube-dependent tests MUST use mocks (patch at adapter module level)
- E2E tests only run on PRs, never on direct push to main
- Branch naming: `feat/*`, `fix/*`, `refactor/*`
- PR workflow only — never push to main
- TDD: failing test first, then implementation

## Key File Structure (post-decouple)

```
src/langmine/
├── domain/              # Language-agnostic core
├── adapters/            # Language-agnostic adapters only
├── languages/
│   └── chinese/         # 6 source files + 4 test files
│       ├── service.py   # ChineseLanguageService
│       ├── dictionary.py # CcCedictAdapter
│       ├── frequency.py  # SubtlexChAdapter + JiebaFrequencyAdapter
│       ├── hsk.py        # HSK proficiency data
│       └── data/         # CC-CEDICT + SUBTLEX corpus
├── language_factory.py  # Single switch point for language loading
├── web/                 # No language-specific code
├── pipeline.py          # Accepts ports, language-agnostic
├── cli.py               # Uses factory, no hardcoded imports
└── config.py            # hsk_bootstrap removed
tests/
├── languages/
│   └── chinese/         # 4 test files + data
├── adapters/
├── test_language_factory.py
└── ...
```

## Key Commands

```bash
# Version
langmine --version                        # e.g. "langmine 1.1.0"

# Run all tests
cd /root/projects/langmine
python -m pytest tests/ -q --ignore=tests/test_audio.py --ignore=tests/test_pipeline.py

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
docker build --build-arg VERSION=1.1.0 -t langmine:1.1.0 .
```

## Container Notes

After Docker container reset:
```bash
apt-get install -y gh libnspr4 libnss3 libatk1.0-0t64 libatk-bridge2.0-0t64 \
  libcups2t64 libdrm2 libdbus-1-3 libxkbcommon0 libxcomposite1 libxdamage1 \
  libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2t64
pip install -e ".[dev]"
```

## Decoupling Plan

See `.hermes/plans/2026-05-30-decouple-chinese.md` for full phase breakdown.
