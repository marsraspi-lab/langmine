# Handoff — 2026-06-02 (Svelte 5 Runes Migration)

## Where We Are

**Svelte 5 runes migration complete.** Merged to `main`.

- **`main`:** v1.7.3 — 248 pytest + 57 E2E.
- **What's new (Runes):** `stores.js` → `stores.svelte.js`. All shared state in single `$state({})` object exported as `app`. Components use `app.storeName` (no `$` prefix). Derived values via `$state` + `$effect` getter functions. Direct property assignment replaces `.set()`/`.update()`. See CONTRIBUTING.md for full state reference.
- **What's new (M24):** `POST /api/sentences/<id>/merge-with-previous` — merges sentence B into the previous sentence A. Concatenates `text`, `text_segmented`, `reading`, `translation_de`. Spans timing from A's `start_ms` to B's `end_ms`. Soft-deletes B. Reclassifies the merged sentence. Frontend: ⬆️ Merge button on non-first sentence cards in curation view.
- **What's new (M23):** Word splitting via editable `text_segmented` — click the segmented text to edit word boundaries with spaces. Spaces converted to ` / ` separator on save. Sentence reclassified after split.
- **What's new (M22):** "Add Sentences" — `reclassify_all()` endpoint reclassifies all sentences for a video, paginated (offset/limit). "🔄 Reclassify & sort" and "+ Add more sentences" buttons in curation view.
- **What's new (M21):** HSK bootstrap — pre-marks HSK words as `known` based on configured proficiency level.
- **What's new (M20):** Manual proper name marking — `PATCH /api/vocab/<word>` supports `{status: "proper-name"}` and `{proper_name: true/false}`. 👤 Mark as proper name / ❌ Not a proper name buttons in word popovers. Guard prevents re-detection of dismissed proper names.
- **What's new (M19):** Client-side curation — `knownWords`/`learningWords`/`ignoredWords` Svelte hashmaps. `curatedSentences` derived store computes status client-side. All sentences visible. Instant word highlighting. Removed server cascade for word status changes.

## What Changed (M19–M24)

### M19: Client-Side Curation
- Svelte writable stores: `knownWords`, `learningWords`, `ignoredWords` (hashmaps)
- `curatedSentences` derived store: computes `computedStatus` per sentence from vocabulary
- All sentences visible in "All" tab regardless of status
- Instant word highlighting — no server roundtrip on word status change

### M20: Manual Proper Names
- `PATCH /api/vocab/<word>` now accepts `{status: "proper-name"}` and `{proper_name: true/false}`
- Popover buttons: "👤 Mark as proper name", "❌ Not a proper name"
- `_words_array` guard in `classifier.py` excludes `("known", "ignored", "proper-name", "learning")`
- 3 new E2E tests for proper-name marking/dismissal

### M21: HSK Bootstrap
- `_bootstrap_hsk()` pre-marks HSK words as `known` using language extension proficiency data
- Words stamped with `hsk_level` and `frequency_rank` from language data

### M22: Add Sentences
- `SentenceClassifier.reclassify_all(video_id)` — domain method
- `POST /api/videos/<id>/reclassify?offset=N&limit=M` — returns `{sentences, has_more, total}`
- Frontend: "🔄 Reclassify & sort" and "+ Add more sentences" buttons
- `reclassifyAndLoad` store action with pagination state

### M23: Word Splitting
- Click `text_segmented` to inline-edit with spaces as word boundaries
- Save converts `"word1 word2 word3"` → `"word1 / word2 / word3"`
- `_reclassify_from_segmented()` reclassifies after edit
- E2E: edits "我们 一般 早上 起床" → "我们 一 般 早上 起床" (split 一般)

### M24: Sentence Joining
- `POST /api/sentences/<id>/merge-with-previous` — backend endpoint
- Finds previous sentence by `start_ms` ordering, concatenates all fields
- Soft-deletes previous sentence, reclassifies merged via `_reclassify_from_segmented()`
- `_get_sentence_or_404()` helper
- Frontend: `mergeWithPrevious()` API + ⬆️ Merge button (visible when `idx > 0`)
- `onMerge` handler in CardList: API call → reload → toast
- E2E: verifies merge button visibility, first-sentence guard, merge POST

## Architecture Rules (unchanged)

- Hexagonal: `domain/` never imports from `adapters/` or `web/`
- `domain/` never imports from `languages/`
- `web/` never imports from `languages/`
- Language packages never cross-import each other
- Language packages never import from `web/`
- Only `language_factory.py` imports from `languages/` — THE single switch point
- `routes.py` must not import from `adapters/` (wire through Flask config)
- TDD: failing test first, then implementation

## Key Commands

```bash
# Run all tests
cd /workspace/langmine
python -m pytest tests/ -q --ignore=tests/test_audio.py

# Run E2E tests
cd src/langmine/web/frontend
PLAYWRIGHT_BROWSERS_PATH=/opt/playwright-browsers npx playwright test

# Build frontend
cd src/langmine/web/frontend && npm run build

# Verify architecture isolation
grep -r "from langmine.languages" src/langmine/domain/      # must be EMPTY
grep -r "from langmine.languages" src/langmine/web/         # must be EMPTY
grep -r "from langmine.adapters" src/langmine/domain/       # must be EMPTY
```
