# Handoff — Session End 2026-05-30

## Where We Are

**M0–M9 complete.** All 31 Playwright E2E tests + 138 pytest tests pass.

**Next: M10 — Reading Mode + Keyboard Shortcuts**
Plan: `.hermes/plans/2026-05-29-m10-m14-reading-cloze-image-preview-ruby.md`

Some M10 scaffolding already exists:
- `GET /api/videos/<id>/transcript` endpoint (routes.py line 139)
- `TranscriptView.svelte` component (basic structure)
- Keyboard shortcut bar in the plan

## What We Just Did

Two PRs merged into main:

1. **PR #2** — E2E fixes: added `npm run build` to CI e2e job, fixed test order dependency (word highlighting tests before state-modifying tests), fixed stale toast pollution.

2. **PR #3** — Extracted page objects: `e2e/pages.js` with MainPage, CurationPage, SettingsPage, VocabPage. Tests now read like intent instead of raw locators.

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

## Related Skills

- `langmine-development` — project conventions, testing patterns, CI quirks
- `writing-plans` — for M10 implementation planning
- `test-driven-development` — strict TDD enforced
