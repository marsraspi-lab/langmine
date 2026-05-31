# M19–M24 Implementation Plan — Curation Rework

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Replace server-stored sentence classification with client-side computation from a known-words hashmap. Fix proper name detection, add HSK bootstrap, word splitting, sentence joining, and "Add Sentences" reclassification.

**Architecture:** Client holds `knownWords`/`learningWords`/`ignoredWords` hashmaps. Sentence status (i+1/i0/stashed) is computed locally from `text_segmented` tokens minus known/ignored words. Server is source-of-truth for vocab status only. All sentences visible at all times.

**Tech Stack:** Svelte 5 (stores, $derived), Python 3.11+ (Flask, jieba posseg), SQLite

---

## Agreed Design Decisions

| Decision | Choice |
|----------|--------|
| HSK bootstrap config | `hsk_bootstrap_level` — words ≤ N → known, > N → unknown (not learning). Runs on first classification for the language |
| Hide i0/stashed sentences? | No — all sentences always visible |
| Sentence status computation | Client-side from known-words hashmaps + `text_segmented`. Server is vocab source-of-truth only |
| Word marking cascade | Instant client-side hashmap update. Server updates vocab async. No automatic cascade |
| Reclassification trigger | "Add Sentences" button at end of list. Re-runs classification server-side on ALL sentences in the current video. Sorted by (unknown_count, freq_rank), paginated 50 at a time |
| Proper name fix | Sentence-level `pseg.cut(full_text)`, match token position → POS tag |
| Word splitting | Inline edit of `text_segmented` per sentence. User adds/removes spaces at word boundaries |
| Sentence joining | "Merge with previous" button on every sentence except first. Pair-wise, chains for N-way join. Keep sentence A's media, delete sentence B |

---

## Milestone Structure (Vertical Slices)

### M19: Client-Side Word Status + All Sentences Visible

**User-visible outcome:** After this milestone, all sentences appear in curation. Marking a word known/ignored instantly updates all occurrences across all sentences without a page reload.

### M20: Fix Proper Name Detection

**User-visible outcome:** Person names (李世民, 刘备), place names (北京, 长安) correctly show `[brackets]` instead of being treated as unknown words.

### M21: HSK Bootstrapping

**User-visible outcome:** Set `hsk_bootstrap_level: 3` in Settings → all HSK 1–3 words pre-marked as known during mining and in the vocab table.

### M22: Add Sentences + Reclassification

**User-visible outcome:** Click "➕ Add Sentences" at the bottom of the list → stashed sentences are reclassified against current vocab → best i+1/i+2 candidates appear, paginated 50 at a time.

### M23: Word Splitting

**User-visible outcome:** Click a word → popover → "✂️ Split" → the word breaks into individual characters, each independently status-highlighted.

### M24: Sentence Joining

**User-visible outcome:** Click "Merge with Previous" on a sentence → it joins with the one above, combined text/timing, original media kept, second sentence deleted.

---

## M19: Client-Side Word Status + All Sentences Visible

### Task 1: Create `knownWords` / `learningWords` / `ignoredWords` stores

**Objective:** Add three Svelte writable stores holding `Set<string>` of words by status. Add a `setWordStatus(word, status)` action that updates the relevant set.

**Files:**
- Modify: `src/langmine/web/frontend/src/lib/stores.js`

**Step 1: Add stores and setter**

```javascript
// === New: word status stores (M19) ===

/** @type {import('svelte/store').Writable<Set<string>>} */
export const knownWords = writable(new Set());
/** @type {import('svelte/store').Writable<Set<string>>} */
export const learningWords = writable(new Set());
/** @type {import('svelte/store').Writable<Set<string>>} */
export const ignoredWords = writable(new Set());

/**
 * Move a word between status sets.
 * Mutates the sets in place and triggers reactive updates.
 */
export function setWordStatus(word, newStatus) {
  const removeFrom = {
    known: knownWords,
    learning: learningWords,
    ignored: ignoredWords,
  };
  const addTo = removeFrom[newStatus];
  // Remove from all sets first
  for (const [status, store] of Object.entries(removeFrom)) {
    if (status !== newStatus || !store) continue;
    store.update(s => {
      const next = new Set(s);
      if (status === newStatus) next.add(word);
      else next.delete(word);
      return next;
    });
  }
  // Also remove from the other two
  for (const [status, store] of Object.entries(removeFrom)) {
    if (status === newStatus) continue;
    store.update(s => {
      const next = new Set(s);
      next.delete(word);
      return next;
    });
  }
}

/**
 * Compute sentence display status from known/learning/ignored sets.
 * Returns one of: 'i1', 'i2', 'i3', 'i0' (counted by unknown words),
 * or 'stashed' for 3+ unknowns.
 */
export function computeSentenceStatus(tokens, nonWordSet, knownSet, ignoredSet) {
  const content = tokens.filter(t => !nonWordSet.has(t));
  const unknown = content.filter(t => !knownSet.has(t) && !ignoredSet.has(t));
  const count = unknown.length;
  if (count === 0) return 'i0';
  if (count <= 3) return `i${count}`;
  return 'stashed';
}
```

### Task 2: Preload known/learning/ignored words from API on app boot

**Objective:** On `loadConfig()` (or separately), fetch the full known/learning/ignored vocabulary and populate the hashmap stores.

**Files:**
- Modify: `src/langmine/web/frontend/src/lib/api.js`
- Modify: `src/langmine/web/frontend/src/lib/stores.js`

**Step 1: Add API endpoint for listing vocab by status**

Backend: add `GET /api/vocab/statuses` that returns `{"known": [...], "learning": [...], "ignored": [...]}`.

**Step 2: Add `listVocabStatuses()` to api.js**

```javascript
async function get(path) { /* existing */ }
// ...
export async function listVocabStatuses() {
  return get('/vocab/statuses');
}
```

**Step 3: Load hashmap on app boot**

In `stores.js`, add and call `loadWordStatuses()`:

```javascript
import { listVocabStatuses } from './api.js';

export async function loadWordStatuses() {
  try {
    const data = await listVocabStatuses();
    knownWords.set(new Set(data.known || []));
    learningWords.set(new Set(data.learning || []));
    ignoredWords.set(new Set(data.ignored || []));
  } catch (err) {
    console.error('Failed to load word statuses:', err);
  }
}
```

Call `loadWordStatuses()` from `App.svelte` `onMount`, alongside `loadConfig()` and `loadLanguages()`.

### Task 3: Add `GET /api/vocab/statuses` backend endpoint

**Objective:** Return all vocab words grouped by status.

**Files:**
- Modify: `src/langmine/web/routes.py`
- Create: `tests/test_vocab_statuses.py`

**Step 1: Write failing test**

```python
def test_vocab_statuses_groups_by_status(client):
    """GET /api/vocab/statuses returns words grouped by status."""
    resp = client.get("/api/vocab/statuses")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "known" in data
    assert "learning" in data
    assert "ignored" in data
    assert isinstance(data["known"], list)
```

**Step 2: Implement route**

```python
@app.route("/api/vocab/statuses")
def vocab_statuses():
    persistence = _get_persistence()
    lang = _get_language_code()
    all_words = persistence.list_vocab(page=1, per_page=99999, language_code=lang)
    result = {"known": [], "learning": [], "ignored": []}
    for word in all_words[0]:  # list_vocab returns (items, total)
        if word.status in result:
            result[word.status].append(word.word_simplified)
    return jsonify(result)
```

### Task 4: Remove i0/stashed/deleted filtering — all sentences visible

**Objective:** Change the `All` filter (and all filters) to return ALL sentences regardless of status. Remove server-side status filtering from `getSentences`.

**Files:**
- Modify: `src/langmine/web/routes.py` — `get_video_sentences()` 
- Modify: `src/langmine/web/frontend/src/lib/CardList.svelte`

**Step 1: Change `all` to mean literally all**

In `routes.py`, the `GET /api/videos/<id>/sentences` endpoint already supports `?status=all` which currently filters. Change it so `status=all` or no status parameter returns ALL sentences for the video (including i0, stashed, deleted).

**Step 2: Change frontend filter to all-status**

In `CardList.svelte`, change `loadSentences(id, 'all')` — but verify the backend returns everything.

Add `loadSentences(id, null)` to the api and use it for the initial load.

### Task 5: Client-side sentence status computation in CardList

**Objective:** Replace server-returned `sentence.status` with client-computed status from `text_segmented` + hashmap.

**Files:**
- Modify: `src/langmine/web/frontend/src/lib/CardList.svelte`
- Modify: `src/langmine/web/frontend/src/lib/stores.js`
- Modify: `src/langmine/web/frontend/src/lib/SentenceCard.svelte`

**Step 1: Add derived store for annotated sentences**

In `stores.js`:

```javascript
import { derived } from 'svelte/store';

export const curatedSentences = derived(
  [sentences, knownWords, learningWords, ignoredWords],
  ([$sentences, $knownWords, $learningWords, $ignoredWords]) => {
    return $sentences.map(s => {
      const tokens = (s.text_segmented || '').split(' / ').filter(Boolean);
      const contentWords = tokens;  // non-word filtering done at render
      const unknown = contentWords.filter(w => 
        !$knownWords.has(w) && !$ignoredWords.has(w)
      );
      const learning = contentWords.filter(w => $learningWords.has(w));
      return {
        ...s,
        computedStatus: unknown.length === 0 ? 'i0' 
          : unknown.length === 1 ? 'i1'
          : unknown.length === 2 ? 'i2'
          : unknown.length === 3 ? 'i3'
          : 'stashed',
        wordStatuses: Object.fromEntries(contentWords.map(w => [
          w,
          $knownWords.has(w) ? 'known'
            : $ignoredWords.has(w) ? 'ignored'
            : $learningWords.has(w) ? 'learning'
            : 'unknown'
        ])),
      };
    });
  }
);
```

**Step 2: Use `$curatedSentences` in CardList instead of `$sentences`**

Replace `{$sentences}` in CardList with `{$curatedSentences}`. The filter tabs now filter by `computedStatus`.

### Task 6: Instant word marking updates from popover

**Objective:** When user clicks "Known" / "Ignored" / "Learning" in the word popover, update the client hashmap instantly (no page reload). Also fire an async PATCH to persist server-side.

**Files:**
- Modify: `src/langmine/web/frontend/src/lib/SentenceCard.svelte`
- Modify: `src/langmine/web/frontend/src/lib/TranscriptView.svelte`
- Modify: `src/langmine/web/frontend/src/lib/stores.js`

**Step 1: Create `markWordStatus(word, status)` action in stores.js**

```javascript
export async function markWordStatus(word, status) {
  // 1. Client-side instant update
  setWordStatus(word, status);
  
  // 2. Server-side async persist (fire-and-forget)
  try {
    await updateVocabWord(word, status);
  } catch (err) {
    addToast(`Failed to save: ${err.message}`, 'error');
    // Revert on failure
    // (simplified — in practice you'd re-fetch statuses)
  }
}
```

**Step 2: Update popover buttons**

In both `SentenceCard.svelte` and `TranscriptView.svelte`, change the popover's Known/Ignored/Learning button handlers from `oniknowthis(id)` to `markWordStatus(word, 'known')` etc.

Remove the old `markWordKnown` / `refreshAfterAction` cycle.

### Task 7: Remove server-side cascade on word mark

**Objective:** `PATCH /api/vocab/<word>` no longer triggers `_cascade_word_known`. The cascade is now client-side only. Server just updates the vocab status.

**Files:**
- Modify: `src/langmine/web/routes.py`

Remove the `_cascade_word_known(persistence, word, processor)` calls from `update_vocab_word()`. Keep the `updateVocabWord` function simple: update status, return OK.

### Task 8: Commit M19

```bash
git add -A
git commit -m "feat: client-side word status with all sentences visible"
```

---

## M20: Fix Proper Name Detection

### Task 1: Refactor `is_proper_name` to use sentence-level POS tagging

**Objective:** Instead of calling `pseg.cut(token)` on single tokens (which jieba may further segment), pass the full sentence text to `pseg.cut()` and match tokens by position.

**Files:**
- Modify: `src/langmine/languages/chinese/service.py`
- Modify: `src/langmine/web/routes.py` (thread `full_text` through `_words_array`)
- Modify: `src/langmine/domain/ports.py` (change `is_proper_name` signature?)

**Design decision:** Keep `is_proper_name(token)` signature but add an optional `context_sentence: str = ""` parameter. When provided, use sentence-level POS tagging.

### Task 2: Update `_words_array` to pass sentence text

In `routes.py`, pass `sentence.text` as context:

```python
result["words"] = _words_array(sentence, persistence, processor, sentence.text)
```

Update `_words_array` signature and pass `full_text` to `is_proper_name`.

### Task 3: Commit M20

```bash
git commit -m "fix: proper name detection via sentence-level POS tagging"
```

---

## M21: HSK Bootstrapping

### Task 1: Add `hsk_bootstrap_level` to Config

**Files:**
- Modify: `src/langmine/config.py`
- Modify: `src/langmine/web/routes.py` (ALLOWED set + SettingsPage)
- Modify: `src/langmine/web/frontend/src/lib/SettingsPage.svelte`

### Task 2: Bootstrap known vocab on first classification

**Objective:** When a video is mined for a language with `hsk_bootstrap_level > 0`, pre-fill the vocab table: HSK words ≤ level → status "known", HSK words > level → status "unknown".

**Files:**
- Modify: `src/langmine/pipeline.py` (or new bootstrap function in domain)

### Task 3: Commit M21

---

## M22: Add Sentences + Reclassification

### Task 1: Server-side reclassification endpoint

**Objective:** `POST /api/videos/<id>/reclassify` — re-runs classification on ALL sentences in the video using current `known_words`, returns sorted by (unknown_count ASC, freq_rank ASC), paginated (offset, limit).

### Task 2: Frontend "Add Sentences" button

**Objective:** Button at bottom of CardList. Calls reclassification endpoint, appends results. Tracks offset for pagination.

### Task 3: Commit M22

---

## M23: Word Splitting

### Task 1: Inline edit of `text_segmented` 

**Objective:** Click a word → popover → "✂️ Split" → the `text_segmented` field opens for inline editing. User adds spaces between char boundaries. Save updates the sentence.

**Files:**
- Modify: `src/langmine/web/frontend/src/lib/SentenceCard.svelte`
- Modify: `src/langmine/web/routes.py` (update `EDITABLE_FIELDS`)

### Task 2: Commit M23

---

## M24: Sentence Joining

### Task 1: "Merge with previous" button + API

**Objective:** Button on every sentence except the first. Calls `POST /api/sentences/<id>/merge-with-previous`. Server merges text, timing, keeps sentence A's media, deletes sentence B, logs event.

### Task 2: Frontend refresh after merge

### Task 3: Commit M24

---

## M19 Detailed Tasks

### Task 1: Create `knownWords` / `learningWords` / `ignoredWords` stores

**Objective:** Add three Svelte writable stores holding `Set<string>` of words by status. Add a `setWordStatus(word, status)` action that updates the relevant set.

**Files:**
- Modify: `src/langmine/web/frontend/src/lib/stores.js`

**Step 1: Write failing test**

N/A — stores.js has no test file. This is Svelte store logic tested via E2E.

**Step 2: Add stores and setter**

```javascript
// === New: word status stores (M19) ===

/** @type {import('svelte/store').Writable<Set<string>>} */
export const knownWords = writable(new Set());
/** @type {import('svelte/store').Writable<Set<string>>} */
export const learningWords = writable(new Set());
/** @type {import('svelte/store').Writable<Set<string>>} */
export const ignoredWords = writable(new Set());

/**
 * Move a word between status sets.
 * Updates all three sets atomically.
 */
export function setWordStatus(word, newStatus) {
  for (const [status, store] of Object.entries({
    known: knownWords,
    learning: learningWords,
    ignored: ignoredWords,
  })) {
    store.update(s => {
      const next = new Set(s);
      if (status === newStatus) next.add(word);
      else next.delete(word);
      return next;
    });
  }
}
```

### Task 2: Add `GET /api/vocab/statuses` backend endpoint

**Objective:** Return all vocab words grouped by status.

**Files:**
- Create: `tests/test_vocab_statuses.py`
- Modify: `src/langmine/web/routes.py`

**Step 1: Write failing test**

```python
import pytest
from tests.test_web_api import create_test_app

@pytest.fixture
def client():
    app = create_test_app()
    return app.test_client()

def test_vocab_statuses_returns_grouped_words(client):
    resp = client.get("/api/vocab/statuses")
    assert resp.status_code == 200
    data = resp.get_json()
    for key in ("known", "learning", "ignored"):
        assert key in data
        assert isinstance(data[key], list)

def test_vocab_statuses_empty_when_no_words(client):
    resp = client.get("/api/vocab/statuses")
    data = resp.get_json()
    assert data["known"] == []
```

**Step 2: Run test to verify failure**

```bash
python -m pytest tests/test_vocab_statuses.py -v
# Expected: 404 or 500 — endpoint doesn't exist
```

**Step 3: Implement route**

In `routes.py`, add before the return statement:

```python
@app.route("/api/vocab/statuses")
def vocab_statuses():
    """Return all vocab words grouped by status for client hashmap init."""
    persistence = _get_persistence()
    lang = _get_language_code()
    all_words, _ = persistence.list_vocab(
        page=1, per_page=99999, language_code=lang
    )
    result: dict[str, list[str]] = {"known": [], "learning": [], "ignored": []}
    for word in all_words:
        if word.status in result:
            result[word.status].append(word.word_simplified)
    return jsonify(result)
```

**Step 4: Run test to verify pass**

```bash
python -m pytest tests/test_vocab_statuses.py -v
# Expected: 2 passed
```

**Step 5: Commit**

```bash
git add tests/test_vocab_statuses.py src/langmine/web/routes.py
git commit -m "feat: add GET /api/vocab/statuses endpoint"
```

### Task 3: Preload word statuses on app boot

**Objective:** Fetch statuses from new endpoint and populate hashmap stores.

**Files:**
- Modify: `src/langmine/web/frontend/src/lib/stores.js`
- Modify: `src/langmine/web/frontend/src/App.svelte`

**Step 1: Add `loadWordStatuses()` to stores.js**

```javascript
import { listVocabStatuses } from './api.js';  // add at top

export async function loadWordStatuses() {
  try {
    const data = await listVocabStatuses();
    knownWords.set(new Set(data.known || []));
    learningWords.set(new Set(data.learning || []));
    ignoredWords.set(new Set(data.ignored || []));
  } catch (err) {
    console.error('Failed to load word statuses:', err);
  }
}
```

**Step 2: Call from App.svelte onMount**

Add `import { loadWordStatuses } from './lib/stores.js';` and call `await loadWordStatuses();` after `loadConfig()`.

**Step 3: Build and verify**

```bash
cd src/langmine/web/frontend && npm run build
```

**Step 4: Commit**

```bash
git add src/langmine/web/frontend/src/lib/stores.js src/langmine/web/frontend/src/App.svelte
git commit -m "feat: preload word status hashmaps on app boot"
```

### Task 4: Remove status filtering from sentence API — all visible

**Objective:** `GET /api/videos/<id>/sentences` with `status=all` or no status returns ALL sentences regardless of status.

**Files:**
- Modify: `src/langmine/web/routes.py`
- Modify: `tests/test_routes.py` (if assertions check status filtering)

**Step 1: Change route**

In the `get_video_sentences` handler, change the `status` parameter handling: when `status` is `'all'` or missing, pass `None` to `get_sentences_by_video`, which should return all statuses.

**Step 2: Run pytest**

```bash
python -m pytest tests/test_routes.py -v
```

**Step 3: Build frontend, verify E2E**

```bash
npm run build && npx playwright test
```

**Step 4: Commit**

```bash
git commit -m "feat: all sentences visible regardless of status"
```

### Task 5: Client-side sentence status computation

**Objective:** Add `curatedSentences` derived store that computes `computedStatus` and `wordStatuses` per sentence from the hashmap stores.

**Files:**
- Modify: `src/langmine/web/frontend/src/lib/stores.js`
- Modify: `src/langmine/web/frontend/src/lib/CardList.svelte`
- Modify: `src/langmine/web/frontend/src/lib/SentenceCard.svelte`

**Step 1: Add `curatedSentences` derived store**

```javascript
export const curatedSentences = derived(
  [sentences, knownWords, learningWords, ignoredWords],
  ([$sentences, $knownWords, $learningWords, $ignoredWords]) => {
    return $sentences.map(s => {
      const tokens = (s.text_segmented || '').split(' / ').filter(Boolean);
      const unknown = tokens.filter(w =>
        !$knownWords.has(w) && !$ignoredWords.has(w)
      );
      const count = unknown.length;
      return {
        ...s,
        computedStatus: count === 0 ? 'i0'
          : count === 1 ? 'i1'
          : count === 2 ? 'i2'
          : count === 3 ? 'i3'
          : 'stashed',
        wordStatuses: Object.fromEntries(tokens.map(w => [
          w,
          $knownWords.has(w) ? 'known'
            : $ignoredWords.has(w) ? 'ignored'
            : $learningWords.has(w) ? 'learning'
            : 'unknown'
        ])),
      };
    });
  }
);
```

**Step 2: Use `$curatedSentences` in CardList**

Replace `$sentences` with `$curatedSentences` in CardList.svelte. Filter tabs now filter by `s.computedStatus`.

**Step 3: Update SentenceCard to use `wordStatuses`**

Instead of the `sentence.words` array from the API, use `sentence.wordStatuses` for word highlighting.

**Step 4: Commit**

```bash
git commit -m "feat: client-side sentence status computation from word hashmaps"
```

### Task 6: Instant word marking from popover

**Objective:** Popover "Known" / "Ignored" / "Learning" buttons update the hashmap instantly AND fire async server persist.

**Files:**
- Modify: `src/langmine/web/frontend/src/lib/stores.js`
- Modify: `src/langmine/web/frontend/src/lib/SentenceCard.svelte`
- Modify: `src/langmine/web/frontend/src/lib/TranscriptView.svelte`

**Step 1: Add `markWordStatus()` action**

```javascript
import { updateVocabWord } from './api.js';  // add import

export async function markWordStatus(word, status) {
  // Instant client update
  setWordStatus(word, status);
  
  // Async server persist
  try {
    await updateVocabWord(word, status);
  } catch (err) {
    addToast(`Failed to save: ${err.message}`, 'error');
  }
}
```

**Step 2: Wire popover buttons**

In both SentenceCard and TranscriptView, import `markWordStatus` and change the popover button handlers.

**Step 3: Commit**

```bash
git commit -m "feat: instant word marking with async server persist"
```

### Task 7: Remove server-side cascade on vocab update

**Objective:** `PATCH /api/vocab/<word>` only updates status. No cascade.

**Files:**
- Modify: `src/langmine/web/routes.py`

**Step 1: Remove cascade calls**

In `update_vocab_word()`, remove the `_cascade_word_known()` calls. Keep just the status update and save.

**Step 2: Run pytest**

```bash
python -m pytest tests/ -x -q --ignore=tests/test_audio.py
```

**Step 3: Commit**

```bash
git commit -m "refactor: remove server-side cascade on vocab update"
```

### Task 8: M19 E2E verification

**Objective:** Verify the full flow works end-to-end: load page → all sentences visible → mark word known → all occurrences show green → re-fetch still matches.

**Files:**
- Modify: `src/langmine/web/frontend/e2e/app.spec.js` (add test)

```javascript
test('marking word known updates all occurrences instantly', async ({ page }) => {
  const main = new MainPage(page);
  const curation = new CurationPage(page);
  await page.goto('/');
  await main.selectFirstVideo();
  // All sentences should be visible (not just i+1)
  await expect(curation.chineseText.first()).toBeVisible({ timeout: 5000 });
  // ... click word, mark known, verify all instances changed
});
```

### Task 9: Final M19 commit

```bash
git commit -m "test: E2E for instant word marking across all sentences"
```

---

## Remaining Milestones (M20–M24)

Detailed tasks for M20–M24 will be written after M19 ships. The architecture changes in M19 are significant enough that M20–M24 tasks need to be verified against the new code structure.

Key notes for later:
- **M20:** `is_proper_name` fix is a 2-file change (service.py + routes.py threading). 
- **M21:** HSK bootstrap is a config field + `pipeline.py` hook.
- **M22:** Reclassification endpoint is a new POST route.
- **M23:** `text_segmented` inline edit mirrors existing reading/translation edit pattern.
- **M24:** Merge endpoint is a new POST route + SentenceCard button.
