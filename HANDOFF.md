# Handoff — Session End 2026-05-30 (M14 Complete)

## Where We Are

**M0–M14 all complete.** 203 pytest + 42 Playwright E2E tests pass.

All features merged: mine, classify, curate, translate, export to Anki, screenshots, inline editing, settings, Docker, vocabulary depth, reading mode, cloze export, image search, difficulty preview, ruby annotations + dictionary deep-dive.

## Architecture Rules

- Hexagonal: `domain/` never imports from `adapters/` or `web/`
- `routes.py` must not import from `adapters/` (wire through Flask config)
- YouTube-dependent tests MUST use mocks (patch at adapter module level)
- E2E tests only run on PRs, never on direct push to main
- Branch naming: `feat/*`, `fix/*`, `refactor/*`
- PR workflow only — never push to main
- TDD: failing test first, then implementation

## Key Commands

```bash
# Run all tests
cd /root/projects/langmine
python -m pytest tests/ -q --ignore=tests/test_audio.py --ignore=tests/test_pipeline.py

# Run E2E tests
cd src/langmine/web/frontend
npx playwright test

# Build frontend
cd src/langmine/web/frontend && npm run build
```

## Container Notes

After Docker container reset:
```bash
apt-get install -y gh libnspr4 libnss3 libatk1.0-0t64 libatk-bridge2.0-0t64 \
  libcups2t64 libdrm2 libdbus-1-3 libxkbcommon0 libxcomposite1 libxdamage1 \
  libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2t64
pip install -e ".[dev]"
```
