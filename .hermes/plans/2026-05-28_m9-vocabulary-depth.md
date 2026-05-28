# M9: Vocabulary Depth

**Goal:** Give users visibility and control over their vocabulary — highlight word status on sentence cards, browse/manage words on a dedicated page, and cascade status changes through the sentence list.

**Date:** 2026-05-28

---

## Decisions (from grilling)

| # | Decision | Choice |
|---|----------|--------|
| 1 | Word highlighting | `words` array in sentence API response: `[{token, status, frequency_rank, hsk_level}]` |
| 2 | Vocab page | Third nav tab, 200-word blocks sorted by frequency, HSK level badges (1–6) |
| 3 | HSK data | Bundled CSV/JSON in `data/hsk/`, old HSK 2.0 (6 levels, ~5K words) |
| 4 | Vocab API | `GET /api/vocab` paginated + `GET /api/vocab/:word` for detail |
| 5 | Cascade | Marking known cascades: i+1→i0, stash n+2→n+1, reclassify affected sentences |
| 6 | New port methods | `list_vocab()`, `get_sentences_by_word()` |
| 7 | Word toggle UI | Inline on sentence cards + dedicated vocab page |

---

## Files to create

| File | Purpose |
|------|---------|
| `data/hsk/hsk_levels.json` | HSK 2.0 word list (word → level mapping) |
| `src/langmine/adapters/hsk.py` | HSK adapter — loads JSON, implements `get_hsk_level(word) → int | None` |
| `src/langmine/web/frontend/src/lib/VocabPage.svelte` | Vocab browsing page |
| `src/langmine/web/frontend/src/lib/WordDetail.svelte` | Word detail panel (definitions, sentences) |
| `src/langmine/web/frontend/src/lib/WordStatusBadge.svelte` | Inline word status toggle (known/learning/unknown) |

## Files to modify

| File | Change |
|------|--------|
| `src/langmine/domain/ports.py` | Add `list_vocab()`, `get_sentences_by_word()` to `Persistence` |
| `src/langmine/adapters/sqlite_persistence.py` | Implement new port methods |
| `src/langmine/web/routes.py` | Add `GET /api/vocab`, `GET /api/vocab/:word`, `PATCH /api/vocab/:word`; extend `_sentence_to_dict` with `words` array; cascade logic |
| `src/langmine/web/app.py` | Inject `HskSource` port |
| `src/langmine/domain/services/chinese.py` | Accept `HskSource` in `ChineseLanguageService` |
| `src/langmine/web/frontend/src/App.svelte` | Add Vocab nav tab |
| `src/langmine/web/frontend/src/lib/SentenceCard.svelte` | Render word highlighting, inline status toggle |
| `src/langmine/web/frontend/src/lib/stores.js` | Add vocab store, selectedWord store |
| `src/langmine/web/frontend/src/lib/api.js` | Add vocab API calls |
| `tests/test_vocab_api.py` | New API tests |
| `tests/test_adapters.py` | Test HSK adapter |
| `tests/adapters/test_sqlite_vocab.py` | Test new persistence methods |

---

## New domain port (optional)

An `HskSource` port may not be needed if HSK lookup is just a function loaded at startup. Decision: **keep it simple — just a module-level dict loaded from JSON. No new port.** The `ChineseLanguageService` or `routes.py` imports the dict directly (it's data, not I/O, so no cardinal rule violation).

```python
# data/hsk/hsk_levels.json
{"的": 1, "一": 1, "是": 1, ...}
```

```python
# src/langmine/adapters/hsk.py
import json
from pathlib import Path

_HSK: dict[str, int] = {}

def _load():
    global _HSK
    if _HSK:
        return
    path = Path(__file__).parent.parent.parent.parent / "data" / "hsk" / "hsk_levels.json"
    with open(path) as f:
        _HSK = json.load(f)

def get_hsk_level(word: str) -> int | None:
    _load()
    return _HSK.get(word)
```

---

## Step-by-step

### Step 1: HSK data + adapter

- Create `data/hsk/hsk_levels.json` with HSK 2.0 words
- Create `src/langmine/adapters/hsk.py`
- Add test in `test_adapters.py` (or new `tests/adapters/test_hsk.py`)

### Step 2: New persistence methods (TDD)

- Add `list_vocab()` and `get_sentences_by_word()` to `Persistence` port
- Implement in `SQLitePersistence` and `FakePersistence`
- Add `get_sentences_by_word()` — query sentences where `unknown_word` matches or where word appears in `text` (for detail view: "all sentences containing this word")

### Step 3: Vocab API endpoints

- `GET /api/vocab?page=1&per_page=200&status=all&search=&sort=frequency`
  - Returns: `{words: [...], total: N, page: 1, per_page: 200}`
  - Each word: `{word, pinyin, definition_de, frequency_rank, hsk_level, status, sentence_count}`
- `GET /api/vocab/<word>` — full detail: definitions, all sentences containing the word
- `PATCH /api/vocab/<word>` — `{status: "known"|"learning"}` — updates vocab status, cascades reclassification

### Step 4: Extend sentence response with word data

- Modify `_sentence_to_dict()` to include `words` array
- For each token in `text_segmented`, look up: status (known/learning/unknown), frequency_rank, hsk_level
- Tokenize by splitting `text_segmented` on ` / `

### Step 5: Cascade reclassification

- When `PATCH /api/vocab/<word>` marks a word "known":
  - Find all sentences where this word is the `unknown_word` and status is "i1" → reclassify to "i0"
  - Find all stashed sentences where this word was one of multiple unknowns → reclassify (may become i+1)
  - Call existing `reclassify_stashed()` per affected video
- When marking "learning" → no cascade (word isn't fully known yet)
- When marking "unknown" (removing from vocab) → re-run classifier on affected sentences

### Step 6: SentenceCard word highlighting

- Replace plain `text_segmented` rendering with a loop over `sentence.words`
- Each word gets a CSS class: `.word-known` (green), `.word-learning` (yellow/orange), `.word-unknown` (red)
- Click on a word → popover with: "Mark known" / "Mark learning", frequency badge, HSK level
- Frequency badge: 🔥 core, ⭐ useful, 💎 rare
- HSK badge: small numbered badge (1–6)

### Step 7: Vocab page (Svelte)

- Third nav tab "Vocabulary"
- Word list sorted by frequency, grouped in 200-word blocks
- Each row: word, pinyin, frequency badge, HSK badge, status indicator
- Click row → WordDetail panel slides in from right:
  - Dictionary definitions (DE + EN)
  - Frequency rank + tier
  - HSK level
  - Status toggle (known/learning)
  - List of sentences containing this word (with status badges)
- Search bar (filters by word or pinyin)
- Status filter tabs (All / Known / Learning)
- Sort options: frequency (default), HSK level

### Step 8: E2E tests

- Word highlighting visible on sentence cards
- Toggle word status inline → sentence card updates
- Vocab page loads, shows word blocks
- Search/filter works
- Click word → detail panel shows sentences

---

## Verification

```bash
# All backend tests pass
pytest tests/ -q --ignore=tests/test_audio.py --ignore=tests/test_pipeline.py

# Architecture check
! grep -r "from.*adapters" src/langmine/domain/

# Frontend builds
cd src/langmine/web/frontend && npm run build

# E2E tests
cd src/langmine/web/frontend && npx playwright test
```

---

## Risks

- **HSK data quality** — need a reliable HSK 2.0 word list. Several open-source options exist (hskhsk.com JSON dump, Chinese-Word-Frequency lists). Verify against official HSK vocabulary before bundling.
- **Performance** — `_sentence_to_dict` now does N vocab lookups per sentence. With 50 sentences × 10 words = 500 lookups per page load. SQLite should handle this fine (indexed), but worth benchmarking.
- **Cascade edge cases** — marking a word known could demote multiple i+1 sentences. If a sentence had exactly one unknown word and it's now known → i0. But if a stashed sentence had 3 unknowns and 1 becomes known → it's now i+2 with 2 unknowns → reclassify to i+1 → should appear in curation. The `reclassify_stashed` method may need extending.
