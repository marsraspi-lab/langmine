# SUBTLEX-Powered Vocabulary Page

**Date:** 2026-06-22
**Status:** Approved

## Overview

Replace the current vocab-table-only vocabulary page with one that displays all words from the SUBTLEX frequency list, ordered by frequency, paginated by 100 words. Each word shows its classification status (known/learning/ignored/unknown). Clicking a word opens an anchored popover with translation, pinyin, reclassification actions, and example sentences from mined content.

## Motivation

The current VocabPage only shows words that exist in the `vocab` SQLite table — words the user has already interacted with. This makes discovery of new words to learn impossible. The SUBTLEX corpus (99,124 Chinese words ranked by frequency of use) is the ideal discovery layer: users can browse the most common words, see which ones they know, and add new words to their learning list.

## Architecture

### Data Flow

```
FrequencySource port (list_words)              Dictionary port (lookup)
        │                                               │
        ▼                                               ▼
SubtlexChAdapter                           CC-CEDICT adapter
(language-specific adapter)                (language-specific adapter)
        │                                               │
        ▼                                               ▼
GET /api/vocab/subtlex  ───── new endpoint, accesses ports via current_app.config
        │
        ├── list slice from FrequencySource port
        ├── batch vocab status from Persistence port
        ├── batch reading + definitions from Dictionary port
        ├── batch sentences from Persistence port (unknown_word IN (...), LIMIT 5)
        ├── merge: each word gets status, definitions, sentences
        └── return: { words: [...], total, page, per_page }

Client cache:
        │
        ├── current page of 100 words cached in component state
        ├── popover reads word data from cache (no API call)
        └── reclassification: PATCH /api/vocab/<word> (existing endpoint)

PATCH /api/vocab/<word>  ── existing endpoint (no changes needed)
        │
        ├── upserts vocab row (creates if absent)
        └── returns updated word
```

**No per-word detail endpoint is needed for this feature.** The list endpoint returns everything the popover needs. `GET /api/vocab/<word>` remains unchanged for other consumers.

### Changes by Layer

| Layer | File | Change |
|-------|------|--------|
| **Port** | `domain/ports.py` | Add `list_words()` to `FrequencySource` ABC |
| **Adapter** | `languages/chinese/frequency.py` | Add `_ordered_words` list, `list_words()`, `count_words()` methods |
| **Adapter** | `languages/chinese/jieba_frequency.py` | Add `list_words()` and `count_words()` stubs (port compliance) |
| **Wiring** | `web/app.py` | Inject `FrequencySource` and `Dictionary` into Flask app config |
| **API** | `web/routes/vocab.py` | New `GET /api/vocab/subtlex` endpoint, accesses ports via `current_app.config` |
| **Frontend** | `lib/VocabPage.svelte` | Rewrite: SUBTLEX data source, page cache, page-based pagination |
| **Frontend** | `lib/WordPopover.svelte` | New: anchored word detail popover (reads from cache) |
| **Frontend** | `lib/api.js` | Add `fetchSubtlexVocab()` |
| **Frontend** | `lib/stores.svelte.js` | No changes needed (`markWordStatus` already exists) |

### Port Abstraction

The endpoint works through domain ports — zero language-specific knowledge:

```
current_app.config["LANGMINE_FREQUENCY_SOURCE"]  → FrequencySource port
current_app.config["LANGMINE_DICTIONARY"]        → Dictionary port
current_app.config["LANGMINE_PERSISTENCE"]       → Persistence port (already wired)
```

- `list_words()` is called on the `FrequencySource` port — works with SUBTLEX-CH, jieba, or any future language's frequency list.
- `lookup(word)` is called on the `Dictionary` port for reading + definitions — works with CC-CEDICT or any future dictionary adapter.
- `hsk_level` is already an optional field on `VocabWord` — other languages leave it `null`.
- Adding a new language means providing `FrequencySource` + `Dictionary` adapters. No endpoint changes.

### Performance

- SUBTLEX already loaded at startup (`SubtlexChAdapter.__init__`, ~200ms, one-time)
- `_ordered_words: list[str]` adds ~1MB memory (99K × ~10 bytes avg per word)
- **Page request:** 1 list slice + 1 batch vocab query + 1 batch dictionary lookup + 1 batch sentence query = **<15ms**
- **Filtered views** (status=known etc.): single scan of 99K in-memory list = **~15ms**
- **Popup open:** instant (reads from client-side cache, no network request)
- **Reclassification:** PATCH /api/vocab/<word> = **<5ms**, optimistic UI update in the meantime

## API Design

### `GET /api/vocab/subtlex` (New)

Returns a full page of SUBTLEX words with all detail needed for display and popover — no per-word endpoint calls needed.

Query params:

| Param | Default | Values |
|-------|---------|--------|
| `page` | `1` | integer ≥1 |
| `per_page` | `100` | max 500 |
| `status` | `null` (all) | `known`, `learning`, `ignored`, `unknown` |
| `search` | `""` | substring match on `word_simplified` |

Response (each word is a self-contained object with definitions and sentences):

```json
{
  "words": [
    {
      "word_simplified": "吗",
      "word_traditional": "嗎",
      "reading": "ma",
      "definition_de": "Fragepartikel",
      "definition_en": "question particle",
      "frequency_rank": 42,
      "frequency_badge": "🔥",
      "hsk_level": 1,
      "status": "learning",
      "sentence_count": 15,
      "sentences": [
        {
          "id": 1,
          "text": "你吃饭了吗",
          "reading": "nǐ chīfàn le ma",
          "translation": "Have you eaten?"
        }
      ]
    }
  ],
  "total": 99124,
  "page": 1,
  "per_page": 100
}
```

**Batch lookups (all through ports):**
- **Vocab status:** `Persistence` port — `SELECT word_simplified, status FROM vocab WHERE word_simplified IN (...)` — words not in DB get `status: "unknown"`
- **Dictionary:** `Dictionary` port — `lookup(word)` for all 100 words (in-memory adapter, ~1ms)
- **Sentences:** `Persistence` port — `SELECT * FROM sentences WHERE unknown_word IN (...)` — group by `unknown_word` in Python, cap at 5 per word. Words with no mined sentences get an empty array.

**Filtering logic:**
- `status=null` (all): slice the ranked list at `(page-1)*per_page`, batch-query vocab for those 100 words
- `status=known|learning|ignored`: get the set of words with that status from DB, filter the full SUBTLEX list to only those words, paginate the filtered result
- `status=unknown`: get all classified words from DB (status IN ('known','learning','ignored','proper-name')), filter SUBTLEX to words NOT in that set, paginate
- `search`: scan the full list for substring matches, paginate the matched subset

**Reading (pinyin):**
- `word.reading` — from `Dictionary` port, includes tone marks (mǎ, mà, de)
- `sentences[].reading` — already stored on Sentence model from NLP enrichment, includes tone marks

**German/English preference:** `Dictionary` port returns `definition_de` when available. `definition_en` is always populated as fallback. For Chinese, the CC-CEDICT adapter auto-detects German entries; other language adapters follow the same contract.

### `PATCH /api/vocab/<word>` (Existing, No Changes)

Used for reclassification. Must upsert: create the vocab row if absent, update status if present. The existing `save_vocab_word` already uses upsert semantics — verify the PATCH handler uses it, not a plain UPDATE.

## Frontend Design

### VocabPage.svelte (Rewrite)

**Layout:**

```
┌──────────────────────────────────────────────────────┐
│  [All 99,124]  [Known 1,234]  [Learning 340]  ...   │  ← status filter tabs
│  🔍 Search...                                        │  ← search input (300ms debounce)
│                                                      │
│  #     Word          Reading       Freq       Status │
│  ────────────────────────────────────────────────── │
│  1     的            de            🔥#1       ● kn   │  ← clickable rows
│  2     我            wǒ            🔥#2       ● kn   │
│  42    吗            ma            🔥#42      ◌ un   │
│  ...                                                 │
│                                                      │
│  [◀◀ First]  [◀ Prev]  Page [__42_] of 992  [Next ▶] [Last ▶▶]  │
└──────────────────────────────────────────────────────┘
```

**Filter tabs:** All, Known, Learning, Ignored, Unknown — each shows count. Active tab highlighted. Switching tabs resets to page 1.

**Word rows:** Each row shows rank number, word text, reading (pinyin), frequency badge with rank, status indicator (colored dot + label). Click opens WordPopover.

**Pagination bar:**
- `◀◀ First` — jump to page 1 (disabled when on page 1)
- `◀ Prev` — previous page (disabled when on page 1)
- `[___42_]` — editable input field, type number and press Enter to jump
- `Next ▶` — next page (disabled when on last page)
- `Last ▶▶` — jump to last page (disabled when on last page)

**States:**
- Loading: spinner
- Empty (no results for filter/search): "No words found" message
- Error: error banner with retry button

### WordPopover.svelte (New)

Anchored popover, positioned absolutely relative to the clicked row or list container. Reuses positioning pattern from `SentenceCard.svelte` word popover.

```
       ┌─────────────────────────────┐
       │  ✕                          │  ← close button
       │  吗  ma                     │  ← word + reading
       │  🔥 #42  HSK 1              │  ← frequency + HSK badges
       │                             │
       │  DE: Fragepartikel          │  ← German definition (primary)
       │  EN: question particle      │  ← English definition (fallback)
       │                             │
       │  Status: ● unknown          │  ← current status
       │  [Mark Known] [Learning]    │  ← reclassification buttons
       │  [Ignore]                   │     (current status button disabled)
       │                             │
       │  Example sentences (3):     │
       │  ┌───────────────────────┐  │
       │  │ 你吃饭了吗              │  │  ← sentence text
       │  │ nǐ chīfàn le ma       │  │  ← sentence reading (pinyin)
       │  │ Hast du gegessen?     │  │  ← sentence translation
       │  └───────────────────────┘  │
       │  ┌───────────────────────┐  │
       │  │ 你好吗                 │  │
       │  │ nǐ hǎo ma             │  │
       │  │ Wie geht es dir?      │  │
       │  └───────────────────────┘  │
       └─────────────────────────────┘
```

**Behavior:**
- Opens on word row click, positioned near the clicked row
- **Reads word data from client-side page cache** (no network request — instant open)
- Close on: X button, click outside, Escape key
- Reclassification calls `markWordStatus(word, status)` from store (optimistic SvelteSet update + PATCH to API)
- On reclassification success, the cached word's status is updated in place so the row dot reflects the change
- If the user navigates to a different page, the cache is replaced with the new page's data

**States:**
- Word found in cache: instant render, all data shown
- Word not in cache (edge case): close popover and re-fetch the page
- Empty sentences: "No example sentences yet" message
- Reclassification error: toast notification (handled by store)

### api.js Addition

```js
fetchSubtlexVocab(page, perPage, status, search)  // GET /api/vocab/subtlex
```

### stores.svelte.js

No changes. Existing `markWordStatus(word, status)` handles:
- Optimistic SvelteSet mutation (remove from old, add to new)
- API persist via `updateVocabWord()`
- Error toast on failure

## Implementation Order

1. **Port + Adapters:** Add `list_words()` to `FrequencySource` and both adapters
2. **API:** New `GET /api/vocab/subtlex` endpoint returning full word detail with sentences
3. **api.js:** Add `fetchSubtlexVocab()`
4. **WordPopover.svelte:** New component (reads from client cache)
5. **VocabPage.svelte:** Rewrite with SUBTLEX data, page cache, pagination, popover integration
6. **Tests:** Backend tests for new endpoint + frontend Playwright tests
