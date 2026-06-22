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
SUBTLEX file (99K words, GB18030)
        │
        ▼
SubtlexChAdapter._ordered_words: list[str]   ← ranked 1..99124 (already in memory)
        │
        ├── list_words(offset, limit, status_filter, search)
        │
        ▼
GET /api/vocab/subtlex  ────────────────────── new endpoint
        │
        ├── slice: 100 words from ranked list
        ├── batch query vocab table for status + sentence counts
        ├── batch query CC-CEDICT for reading (pinyin)
        ├── merge: each word gets status (unknown if not in DB)
        └── return: { words: [...], total, page, per_page }

GET /api/vocab/<word>  ─────────────────────── existing endpoint, enhanced
        │
        ├── dictionary lookup (CC-CEDICT) if no stored definition
        ├── sentence query (LIMIT 5)
        ├── sentences nested inside word object
        └── return: { word: {..., sentences: [...]} }
```

### Changes by Layer

| Layer | File | Change |
|-------|------|--------|
| **Port** | `domain/ports.py` | Add `list_words()` to `FrequencySource` ABC |
| **Adapter** | `languages/chinese/frequency.py` | Add `_ordered_words` list, `list_words()`, `count_words()` methods |
| **Adapter** | `languages/chinese/jieba_frequency.py` | Add `list_words()` and `count_words()` stubs (port compliance) |
| **Dictionary** | `languages/chinese/dictionary.py` | Add `get_reading(word)` helper for pinyin-only lookup |
| **API** | `web/routes/vocab.py` | New `GET /api/vocab/subtlex`; enhance `GET /api/vocab/<word>` |
| **Frontend** | `lib/VocabPage.svelte` | Rewrite: SUBTLEX data source, page-based pagination |
| **Frontend** | `lib/WordPopover.svelte` | New: anchored word detail popover |
| **Frontend** | `lib/api.js` | Add `fetchSubtlexVocab()` |
| **Frontend** | `lib/stores.svelte.js` | No changes needed (`markWordStatus` already exists) |

### Performance

- SUBTLEX already loaded at startup (`SubtlexChAdapter.__init__`, ~200ms, one-time)
- `_ordered_words: list[str]` adds ~1MB memory (99K × ~10 bytes avg per word)
- **Per-page request:** 1 list slice + 1 batch SQL query + 1 batch dictionary lookup = **<10ms**
- **Popup detail:** 1 dictionary lookup + 1 sentence query (LIMIT 5) = **<5ms**
- **Filtered views** (status=known etc.): single scan of 99K in-memory list = **~15ms**

## API Design

### `GET /api/vocab/subtlex` (New)

Query params:

| Param | Default | Values |
|-------|---------|--------|
| `page` | `1` | integer ≥1 |
| `per_page` | `100` | max 500 |
| `status` | `null` (all) | `known`, `learning`, `ignored`, `unknown` |
| `search` | `""` | substring match on `word_simplified` |

Response:

```json
{
  "words": [
    {
      "word_simplified": "的",
      "word_traditional": "",
      "reading": "de",
      "frequency_rank": 1,
      "frequency_badge": "🔥",
      "hsk_level": 1,
      "status": "known",
      "sentence_count": 42
    }
  ],
  "total": 99124,
  "page": 1,
  "per_page": 100
}
```

**Filtering logic:**
- `status=null` (all): slice the ranked list at `(page-1)*per_page`, batch-query vocab for those 100 words
- `status=known|learning|ignored`: get the set of words with that status from DB, filter the full SUBTLEX list to only those words, paginate the filtered result
- `status=unknown`: get all classified words from DB (status IN ('known','learning','ignored','proper-name')), filter SUBTLEX to words NOT in that set, paginate
- `search`: scan the full list for substring matches, paginate the matched subset

**Reclassification of unknown words:** When the user marks a SUBTLEX word as known/learning/ignored via the popover, the word may not yet exist in the `vocab` table. The `PATCH /api/vocab/<word>` endpoint must upsert: create the vocab row if absent, update status if present. The existing `save_vocab_word` already uses upsert semantics — ensure the PATCH handler uses it, not a plain UPDATE.

**Definitions are NOT included in list view** (expensive to look up 100 at a time). Only `reading` (pinyin) is batch-looked up from CC-CEDICT.

### `GET /api/vocab/<word>` (Enhanced)

Existing endpoint with two enhancements:

1. **Dictionary fallback:** If stored `definition_de` is empty, look up CC-CEDICT and return both `definition_de` and `definition_en`. Result is NOT persisted back to DB.
2. **Sentences nested:** `sentences` array is moved inside the `word` object.
3. **Sentences capped:** LIMIT 5.

Response:

```json
{
  "word": {
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
}
```

**Reading (pinyin):**
- `word.reading` — from CC-CEDICT dictionary, includes tone marks (mǎ, mà, de)
- `sentences[].reading` — already stored on Sentence model from NLP enrichment, includes tone marks
- Word reading is batch-looked up for list view; sentences always had reading

**German/English preference:** Dictionary returns `definition_de` when available (auto-detected in CC-CEDICT entries). `definition_en` is always populated as fallback.

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
- Fetches `GET /api/vocab/<word>` on open
- Close on: X button, click outside, Escape key
- Reclassification calls `markWordStatus(word, status)` from store (optimistic update, API persist)
- Reclassification immediately updates the word's status dot in the list behind the popover

**States:**
- Loading: spinner inside popover
- Error: inline error message with retry
- Empty sentences: "No example sentences yet" message

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
2. **API:** New `/api/vocab/subtlex` endpoint + enhance `GET /api/vocab/<word>`
3. **api.js:** Add `fetchSubtlexVocab()`
4. **WordPopover.svelte:** New component
5. **VocabPage.svelte:** Rewrite with SUBTLEX data, pagination, popover integration
6. **Tests:** Backend tests for new endpoint + frontend Playwright tests
