# Handoff — Session End 2026-05-30 (M10 Complete)

## Where We Are

**M10 complete.** All 154 pytest + 37 Playwright E2E tests pass.

PR #4 (feat/m10-testing) open for merge — adds transcript endpoint tests + reading mode E2E tests.

**Next: M11 — Cloze Deletion Export**

## What We Just Did

Added test coverage for M10 reading mode:

1. **tests/test_web_transcript.py** — 6 unit tests for `GET /api/videos/:id/transcript`
2. **e2e/pages.js** — ReadingPage page object
3. **e2e/app.spec.js** — 6 E2E tests: sentence count, word highlighting, popover open/close (Escape), `?` legend toggle, `T` translation toggle

## Key Commands

```bash
# Run all tests
cd /root/projects/langmine
python -m pytest tests/ -q --ignore=tests/test_audio.py --ignore=tests/test_pipeline.py

# Run E2E tests (needs flask + chromium deps)
cd src/langmine/web/frontend
npx playwright test

# Build frontend
cd src/langmine/web/frontend && npm run build
```

## Architecture Rules

- Hexagonal: `domain/` never imports from `adapters/` or `web/`
- `routes.py` must not import from `adapters/` (wire through Flask config)
- YouTube-dependent tests MUST use mocks (patch at adapter module level)
- E2E tests only run on PRs, never on direct push to main
- Branch naming: `feat/*`, `fix/*`, `refactor/*`
- PR workflow only — never push to main

## Container Notes

This Docker container gets reset periodically. After reset:
```bash
apt-get install -y gh libnspr4 libnss3 libatk1.0-0t64 libatk-bridge2.0-0t64 \
  libcups2t64 libdrm2 libdbus-1-3 libxkbcommon0 libxcomposite1 libxdamage1 \
  libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2t64
pip install -e ".[dev]"
```
