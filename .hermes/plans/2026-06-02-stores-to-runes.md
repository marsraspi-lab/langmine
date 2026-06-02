# Store → Runes Migration Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Migrate all 22 writable + 2 derived Svelte stores in `stores.js` to Svelte 5 runes (`$state`, `$derived`, `$effect`) in a new `stores.svelte.js` module, then update all 8 components to drop the `$` auto-subscription prefix.

**Architecture:** Replace `svelte/store` (writable/derived/.set/.update/.subscribe) with Svelte 5 module-level runes (.svelte.js file with `$state`, `$derived`, `$effect`). Module-level `$state` in a `.svelte.js` file creates shared reactive state — same singleton semantics as the current stores. Components will read values directly without `$` prefix, and mutate via direct assignment instead of `.set()`/`.update()`.

**Tech Stack:** Svelte 5.55.5 (already installed), ESM modules

---

## Agreed Design Decisions

| Decision | Choice |
|----------|--------|
| File extension | `.svelte.js` (required for module-level `$state` runes) |
| Keep or delete old `stores.js` | Delete after migration verified |
| Set objects (`knownWords`, etc.) | Use `$state(new Set())` — `.add()`/`.delete()` are reactive on `$state` values |
| Derived store `curatedSentences` | `$derived(...)` — auto-tracks dependencies, same computation logic |
| Side effects (theme localStorage) | `$effect(() => { ... })` — runs whenever dependencies change |
| Manual subscriptions (lines 343-349) | Remove entirely — direct reads from `.svelte.js` exports work everywhere |
| Non-component access pattern | Direct reads + function calls work from any `.js` file |
| E2E tests | No changes needed — DOM output is identical |

---

## Pre-Migration Checklist

- [ ] Verify `svelte` 5.55.5 in `package.json` ✓ (already confirmed)
- [ ] Verify no `svelte/store` imports exist outside `stores.js` 
- [ ] 247 unit + 58 E2E tests passing on main ✓ (confirmed after PR #33 merge)

---

## Tasks

### Task 1: Create stores.svelte.js with $state declarations

**Objective:** Create the new module with all 22 writable stores converted to `$state()` runes.

**Files:**
- Create: `src/langmine/web/frontend/src/lib/stores.svelte.js`

**Step 1: Create the file with all $state declarations**

```js
// stores.svelte.js — Svelte 5 runes (module-level shared state)

// --- Writables → $state ---

export const videos = $state([]);
export const sentences = $state([]);
export const selectedVideoId = $state(null);
export const currentFilter = $state('all');
export const mineStatus = $state('');
export const mining = $state(false);
export const exportStatus = $state('');
export const exporting = $state(false);
export const toasts = $state([]);
export const config = $state({});
export const theme = $state(
  (typeof localStorage !== 'undefined' && localStorage.getItem('langmine-theme')) || 'dark'
);
export const currentView = $state('curation');
export const vocabSearchQuery = $state('');
export const languages = $state([]);
export const currentLanguage = $state('zh');
export const knownWords = $state(new Set());
export const learningWords = $state(new Set());
export const ignoredWords = $state(new Set());
export const readingMode = $state(false);
export const reclassifyOffset = $state(0);
```

**Verification:** File exists and exports all 21 state values (count them). No `svelte/store` import.

---

### Task 2: Add derived store curatedSentences

**Objective:** Convert the `derived()` store to `$derived()`.

**Files:**
- Modify: `src/langmine/web/frontend/src/lib/stores.svelte.js`

**Step 1: Add the $derived computation**

```js
// --- Derived → $derived ---

export const curatedSentences = $derived(
  sentences.map(s => {
    const tokens = (s.text_segmented || '').split(' / ').filter(Boolean);
    const unknown = tokens.filter(w =>
      !knownWords.has(w) && !ignoredWords.has(w)
    );
    const count = unknown.length;
    let computed = count === 0 ? 'i0'
      : count === 1 ? 'i1'
      : count === 2 ? 'i2'
      : count === 3 ? 'i3'
      : 'stashed';
    if (s.status === 'deleted' || s.status === 'kept' || s.status === 'exported') {
      computed = s.status;
    }
    return {
      ...s,
      computedStatus: computed,
      wordStatuses: Object.fromEntries(tokens.map(w => [
        w,
        knownWords.has(w) ? 'known'
          : ignoredWords.has(w) ? 'ignored'
          : learningWords.has(w) ? 'learning'
          : 'unknown'
      ])),
    };
  })
);
```

Note: `$derived` in a `.svelte.js` file auto-tracks all reactive reads — no need to manually list dependencies like `derived([a, b, c], ...)`.

**Verification:** Same computation logic, no dependency array needed.

---

### Task 3: Add selectedVideo derived and $effect for theme

**Objective:** Convert `selectedVideo` derived and `theme.subscribe` side effect.

**Files:**
- Modify: `src/langmine/web/frontend/src/lib/stores.svelte.js`

**Step 1: Add selectedVideo $derived**

```js
export const selectedVideo = $derived(
  videos.find(v => v.id === selectedVideoId) || null
);
```

**Step 2: Add theme persistence $effect**

```js
$effect(() => {
  if (typeof document !== 'undefined') {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('langmine-theme', theme);
  }
});
```

**Verification:** `selectedVideo` is reactive. Theme changes persist to localStorage.

---

### Task 4: Port setWordStatus and toast functions to use direct mutation

**Objective:** Convert `.update()` calls to direct array/Set mutations.

**Files:**
- Modify: `src/langmine/web/frontend/src/lib/stores.svelte.js`

**Step 1: setWordStatus with direct Set mutation**

```js
export function setWordStatus(word, newStatus) {
  // With $state Sets, .add() and .delete() are reactive
  const allStores = { known: knownWords, learning: learningWords, ignored: ignoredWords };
  for (const [status, setObj] of Object.entries(allStores)) {
    if (status === newStatus) {
      setObj.add(word);
    } else {
      setObj.delete(word);
    }
  }
}
```

**Step 2: addToast with direct array push (use spread for reactivity)**

```js
let toastId = 0;

export function addToast(message, type = 'info', duration = 4000) {
  const id = ++toastId;
  toasts.push({ id, message, type });  // $state array: .push() is reactive
  if (duration > 0) {
    setTimeout(() => removeToast(id), duration);
  }
  return id;
}

export function removeToast(id) {
  const idx = toasts.findIndex(t => t.id === id);
  if (idx !== -1) toasts.splice(idx, 1);
}
```

**Verification:** addToast → toast appears. removeToast → toast removed.

---

### Task 5: Port all async functions (loadVideos, loadSentences, mineVideo, etc.)

**Objective:** Convert `.set()` / `.update()` calls to direct assignment.

**Files:**
- Modify: `src/langmine/web/frontend/src/lib/stores.svelte.js`

**Step 1: loadVideos, deleteVideo, selectVideo, loadSentences**

```js
export async function loadVideos() {
  const data = await api.listVideos();
  // Direct assignment replaces .set()
  videos.splice(0, videos.length, ...data.videos);
  // Or simply: videos = data.videos — but that replaces the array reference.
  // Using .splice preserves the $state array reference, which is safer
  // for derived computations that depend on array identity.
}

export async function deleteVideo(id) {
  const { ok, data } = await api.deleteVideo(id);
  if (!ok) {
    addToast(data?.error || 'Failed to delete video', 'error');
    return false;
  }
  addToast('Video deleted', 'success', 2000);
  if (selectedVideoId === id) {
    selectedVideoId = null;
    sentences.length = 0;  // clear array in place
  }
  await loadVideos();
  return true;
}

export async function selectVideo(id) {
  selectedVideoId = id;
  currentFilter = 'all';
  currentView = 'curation';
  await loadSentences(id, 'all');
}

export async function loadSentences(videoId, filter) {
  const data = await api.getSentences(videoId, filter);
  sentences.splice(0, sentences.length, ...data.sentences);
}
```

**Step 2: mineVideo, keepSentence, deleteSentence, markWordKnown, updateSentenceField**

```js
export async function mineVideo(url, file = null, language = '') {
  mining = true;
  mineStatus = '⏳ Mining...';
  try {
    let data;
    for await (const event of api.mineVideoStream(url, file, language)) {
      if (event.error) {
        const err = event.error;
        const msg = err?.message ?? (typeof err === 'string' ? err : JSON.stringify(err));
        const stage = err?.stage;
        const friendly = FRIENDLY_ERRORS[stage];
        if (friendly) {
          throw new Error(msg && msg !== friendly ? msg : friendly);
        }
        throw new Error(msg.length > 200 ? msg.slice(0, 197) + '…' : msg);
      } else if (event.status) {
        mineStatus = `⏳ ${event.status}`;
      } else {
        data = event;
      }
    }
    if (!data) {
      mineStatus = '❌ No result';
      return null;
    }
    mineStatus = `✅ ${data.total_sentences} sentences, ${data.i1_count} i+1`;
    await loadVideos();
    if (data.video_id) {
      await selectVideo(data.video_id);
    }
    return data;
  } catch (err) {
    console.error('[mine]', err);
    mineStatus = `❌ ${err.message}`;
    return null;
  } finally {
    mining = false;
  }
}

export async function keepSentence(id) {
  await api.updateSentence(id, 'kept');
  await refreshAfterAction();
}

export async function deleteSentence(id) {
  await api.updateSentence(id, 'deleted');
  await refreshAfterAction();
}

export async function markWordKnown(id) {
  await api.markWordKnown(id);
  await refreshAfterAction();
}

export async function updateSentenceField(id, fields) {
  try {
    await api.updateSentenceFields(id, fields);
    await refreshAfterAction();
    addToast('Saved ✓', 'success', 2000);
  } catch (err) {
    addToast(`Failed: ${err.message}`, 'error', 4000);
    throw err;
  }
}
```

**Verification:** Each function compiles with no `writable.set()` or `writable.update()` calls.

---

### Task 6: Port remaining functions (config, languages, export, vocab)

**Objective:** Convert remaining async/store-mutating functions.

**Files:**
- Modify: `src/langmine/web/frontend/src/lib/stores.svelte.js`

**Step 1: loadConfig, loadLanguages, selectLanguage**

```js
export async function loadConfig() {
  try {
    const data = await api.getConfig();
    Object.assign(config, data);  // mutate config object in place
    if (data.source_language) {
      currentLanguage = data.source_language;
    }
  } catch (err) {
    console.error('Failed to load config:', err);
  }
}

export async function loadLanguages() {
  try {
    const data = await api.listLanguages();
    languages.splice(0, languages.length, ...data.languages);
  } catch (err) {
    console.error('Failed to load languages:', err);
  }
}

export async function selectLanguage(code) {
  if (code === currentLanguage) return;
  try {
    await api.updateConfig({ source_language: code });
    currentLanguage = code;
    config.source_language = code;
    addToast(`Switched to ${code}`, 'info', 2000);
    await loadVideos();
    if (selectedVideoId) {
      await loadSentences(selectedVideoId, currentFilter);
    }
  } catch (err) {
    addToast(`Failed to switch language: ${err.message}`, 'error');
  }
}
```

**Step 2: reclassifyAndLoad, saveConfig, toggleTheme, exportAnki, loadWordStatuses, markWordStatus**

```js
export async function reclassifyAndLoad(videoId, offset = 0, limit = 50) {
  try {
    const res = await api.reclassifySentences(videoId, offset, limit);
    if (res.ok) {
      const { sentences: newSentences, total } = res.data;
      if (offset === 0) {
        sentences.splice(0, sentences.length, ...newSentences);
      } else {
        sentences.push(...newSentences);
      }
      reclassifyOffset = offset + newSentences.length;
      return { hasMore: reclassifyOffset < total, total };
    } else {
      addToast('Reclassification failed', 'error');
      return { hasMore: false, total: 0 };
    }
  } catch (err) {
    addToast(`Reclassification failed: ${err.message}`, 'error');
    return { hasMore: false, total: 0 };
  }
}

export async function saveConfig(updates) {
  try {
    await api.updateConfig(updates);
    Object.assign(config, updates);
    addToast('Settings saved ✓', 'success', 2000);
  } catch (err) {
    addToast(`Failed to save: ${err.message}`, 'error');
  }
}

export function toggleTheme() {
  theme = theme === 'dark' ? 'light' : 'dark';
}

async function refreshAfterAction() {
  await loadVideos();
  const vidId = selectedVideoId;
  const filter = currentFilter;
  if (vidId) {
    await loadSentences(vidId, filter);
  }
}

export async function exportAnki(videoId, forceUpdateModel = false, cardType = 'basic') {
  exporting = true;
  exportStatus = '⏳ Exporting...';
  try {
    const { ok, data } = await api.exportAnki(videoId, forceUpdateModel, cardType);
    if (!ok) throw new Error(data.error || 'Export failed');
    exportStatus = `✅ ${data.added} new, ${data.duplicates} duplicates`;
  } catch (err) {
    exportStatus = `❌ ${err.message}`;
  } finally {
    exporting = false;
  }
}

export async function loadWordStatuses() {
  try {
    const data = await api.listVocabStatuses();
    knownWords.clear();
    for (const w of data.known || []) knownWords.add(w);
    learningWords.clear();
    for (const w of data.learning || []) learningWords.add(w);
    ignoredWords.clear();
    for (const w of data.ignored || []) ignoredWords.add(w);
  } catch (err) {
    console.error('Failed to load word statuses:', err);
  }
}

export async function markWordStatus(word, status) {
  setWordStatus(word, status);
  try {
    await updateVocabWord(word, status);
  } catch (err) {
    addToast(`Failed to save: ${err.message}`, 'error');
  }
}
```

**Verification:** No `.set()`, `.update()`, or `.subscribe()` calls remain. All state changes are direct assignments or in-place mutations.

---

### Task 7: Remove manual subscription block

**Objective:** Delete the manual `.subscribe()` workaround (lines 343-349 in old stores.js).

**Files:**
- Modify: `src/langmine/web/frontend/src/lib/stores.svelte.js`

**Step 1:** Ensure the manual subscription block is NOT present in `stores.svelte.js`. This is the old pattern:

```js
// ❌ REMOVE — no longer needed with runes
// let $selectedVideoId;
// selectedVideoId.subscribe(v => $selectedVideoId = v);
```

All references to `$selectedVideoId`, `$currentFilter`, `$currentLanguageCode` in the old code have already been replaced with direct reads (`selectedVideoId`, `currentFilter`, `currentLanguage`) in Tasks 5-6.

**Verification:** No `.subscribe()` calls exist in `stores.svelte.js`.

---

### Task 8: Add FRIENDLY_ERRORS and api import

**Objective:** Add the constants and import from api.js.

**Files:**
- Modify: `src/langmine/web/frontend/src/lib/stores.svelte.js`

**Step 1: Top of file**

```js
import { api } from './api.js';
import { updateVocabWord } from './api.js';

const FRIENDLY_ERRORS = {
  transcript: 'Could not download transcript. The video may not have subtitles.',
  classification: 'Could not classify sentences. Try again or check language settings.',
  enrichment: 'Could not generate translations. The language processor may be unavailable.',
  unknown: null,
};
```

**Verification:** File starts with imports, then constants, then $state declarations, then $derived, then $effect, then functions.

---

### Task 9: Build and verify stores.svelte.js compiles

**Objective:** Ensure the new module compiles before touching any components.

**Step 1: Build the frontend**

```bash
cd src/langmine/web/frontend && npm run build
```

Expected: Build succeeds with `stores.svelte.js` (no errors about unresolved imports or syntax).

Note: At this point `stores.js` still exists alongside `stores.svelte.js` — both are valid modules. Build succeeds because no component imports `stores.svelte.js` yet.

---

### Task 10: Update App.svelte — drop $ prefix

**Objective:** Update the root component to import from `stores.svelte.js` and remove all `$` prefixes.

**Files:**
- Modify: `src/langmine/web/frontend/src/App.svelte`

**Step 1: Change import path**

```svelte
<script>
  import { onMount } from 'svelte';
  import Sidebar from './lib/Sidebar.svelte';
  import CardList from './lib/CardList.svelte';
  import { loadVideos, selectedVideoId, toasts, removeToast, theme, toggleTheme, currentView, loadConfig, languages, currentLanguage, loadLanguages, selectLanguage, loadWordStatuses } from './lib/stores.svelte.js';
  import SettingsPage from './lib/SettingsPage.svelte';
  import VocabPage from './lib/VocabPage.svelte';
```

**Step 2: Remove $ prefix from all store reads in the template**

Find every `$variable` and change to `variable`:

| Old | New |
|-----|-----|
| `$currentView` | `currentView` |
| `$selectedVideoId` | `selectedVideoId` |
| `$toasts` | `toasts` |
| `$theme === 'dark'` | `theme === 'dark'` |

Step-by-step changes in App.svelte:

- Line ~28: `$currentView === 'curation'` → `currentView === 'curation'`
- Line ~31: `$currentView === 'settings'` → `currentView === 'settings'`
- Line ~33: `$currentView === 'vocab'` → `currentView === 'vocab'`
- Line ~37: `$theme === 'dark'` → `theme === 'dark'`
- Line ~38: `toggleTheme()` → (unchanged, function call)
- Line ~55: `{#if $selectedVideoId}` → `{#if selectedVideoId}`
- Line ~56: `<CardList videoId={$selectedVideoId} />` → `<CardList videoId={selectedVideoId} />`
- Toasts section: `{#each $toasts as toast}` → `{#each toasts as toast}`

**Verification:** No `$` prefix on any store variable. Build succeeds.

---

### Task 11: Update Sidebar.svelte — drop $ prefix

**Objective:** Update Sidebar to import from `stores.svelte.js` and remove `$` prefixes.

**Files:**
- Modify: `src/langmine/web/frontend/src/lib/Sidebar.svelte`

**Step 1: Change import**

```svelte
import { videos, selectedVideoId, mineStatus, mining, selectVideo, mineVideo,
  exportStatus, exporting, exportAnki, deleteVideo, currentLanguage } from './stores.svelte.js';
```

**Step 2: Remove $ prefix from all store reads**

Find every `$variable` and change to `variable`:

| Old | New |
|-----|-----|
| `$mineStatus` | `mineStatus` |
| `$mining` | `mining` |
| `$exporting` | `exporting` |
| `$exportStatus` | `exportStatus` |
| `$videos` | `videos` |
| `$selectedVideoId` | `selectedVideoId` |
| `$currentLanguage` | `currentLanguage` |

**Step 3: Update function calls that mutate stores**

- `selectVideo(id)` — already a function call, no change
- `mineVideo(url, file, language)` — already a function call, no change
- `deleteVideo(id)` — already a function call, no change
- `exportAnki(videoId, ...)` — already a function call, no change

**Verification:** No `$` prefix on any store variable. Build succeeds.

---

### Task 12: Update CardList.svelte — drop $ prefix

**Objective:** Update CardList to import from `stores.svelte.js` and remove `$` prefixes.

**Files:**
- Modify: `src/langmine/web/frontend/src/lib/CardList.svelte`

**Step 1: Change import**

```svelte
import { sentences, curatedSentences, currentFilter, readingMode, loadSentences, keepSentence, deleteSentence, markWordStatus, reclassifyAndLoad, reclassifyOffset, addToast } from './stores.svelte.js';
```

**Step 2: Remove $ prefix**

| Old | New |
|-----|-----|
| `$curatedSentences` | `curatedSentences` |
| `$currentFilter` | `currentFilter` |
| `$readingMode` | `readingMode` |
| `$sentences` | `sentences` |
| `$reclassifyOffset` | `reclassifyOffset` |

**Step 3: Update direct store mutations in component**

The component has `currentFilter = key` (direct store mutation) — this now works with `$state` instead of `currentFilter.set(key)`.

**Verification:** No `$` prefix. Build succeeds.

---

### Task 13: Update SentenceCard.svelte — drop $ prefix

**Objective:** Update SentenceCard imports and remove `$` prefixes.

**Files:**
- Modify: `src/langmine/web/frontend/src/lib/SentenceCard.svelte`

**Step 1: Change imports**

```svelte
import { updateSentenceField, markWordStatus, currentView, vocabSearchQuery } from './stores.svelte.js';
```

**Step 2: Update store writes**

- `vocabSearchQuery.set(token)` → `vocabSearchQuery = token`
- `currentView.set('vocab')` → `currentView = 'vocab'`

**Verification:** No `.set()` calls. Build succeeds.

---

### Task 14: Update remaining components

**Objective:** Update SettingsPage, VocabPage, TranscriptView.

**Files:**
- Modify: `src/langmine/web/frontend/src/lib/SettingsPage.svelte`
- Modify: `src/langmine/web/frontend/src/lib/VocabPage.svelte`
- Modify: `src/langmine/web/frontend/src/lib/TranscriptView.svelte`

**Step 1: SettingsPage.svelte**

Import change: `'./stores.svelte.js'`

In template: `$config.xxx` → `config.xxx` for all config fields. `saveConfig()` is a function call, no change.

**Step 2: VocabPage.svelte**

Import change: `'./stores.svelte.js'`

`vocabSearchQuery` is used as initial value for `searchQuery` — may need `vocabSearchQuery` read directly:
```js
let searchQuery = $state(vocabSearchQuery);
```
No `$` prefix needed since this is in `<script>`.

**Step 3: TranscriptView.svelte**

Import change: `'./stores.svelte.js'`

- `addToast(...)` — function call, no change
- `currentView = 'vocab'` — direct assignment (was `currentView.set('vocab')`)
- `vocabSearchQuery = token` — direct assignment (was `vocabSearchQuery.set(token)`)
- `markWordStatus(...)` — function call, no change

**Verification:** All imports point to `stores.svelte.js`. No `.set()` calls. Build succeeds.

---

### Task 15: Delete old stores.js

**Objective:** Remove the legacy stores module.

**Files:**
- Delete: `src/langmine/web/frontend/src/lib/stores.js`

**Step 1: Delete the file**

```bash
rm src/langmine/web/frontend/src/lib/stores.js
```

**Step 2: Verify no remaining references**

```bash
grep -r "stores\.js" src/langmine/web/frontend/src/ || echo "No references to stores.js remaining"
```

**Verification:** `grep` returns nothing. Build succeeds.

---

### Task 16: Full test suite

**Objective:** Run unit + E2E tests to verify nothing is broken.

**Step 1: Unit tests**

```bash
cd /workspace/langmine && python -m pytest tests/ -q --ignore=tests/test_audio.py --ignore=tests/test_pipeline.py
```
Expected: 247 passed

**Step 2: Build frontend**

```bash
cd src/langmine/web/frontend && npm run build
```
Expected: Build succeeds, no warnings

**Step 3: E2E tests**

```bash
export PLAYWRIGHT_BROWSERS_PATH=/opt/playwright-browsers && npx playwright test --reporter=line
```
Expected: 58 passed

**Step 4: Commit**

```bash
git add -A
git commit -m "refactor: migrate stores to Svelte 5 runes

- Replace svelte/store (writable/derived) with $state/$derived runes
- stores.js → stores.svelte.js using module-level reactive state
- Remove all $ auto-subscription prefixes from components
- Replace .set()/.update() with direct assignment
- Replace .subscribe() side effects with $effect()
- Remove manual subscription workaround (no longer needed)
- setWordStatus uses reactive Set.add()/delete()"
```

---

## Pitfalls

### Set reactivity with $state

`$state(new Set())` makes the Set **reactive** — `.add()`, `.delete()`, and `.clear()` all trigger reactivity. No need to create new Set instances. But be careful: `knownWords = new Set(...)` replaces the reference, which also works but loses the `$state` proxy. Prefer `.clear()` + `.add()` in a loop, or use `$state` wrapper.

### Array mutation vs replacement

`$state([])` arrays support `.push()`, `.splice()`, `.pop()` reactively. But `sentences = newArray` replaces the reference and is also reactive. Prefer `.splice(0, length, ...items)` over `sentences = [...]` to preserve array identity for `$derived` dependencies — though `$derived` auto-tracks reads so either should work.

### E2E tests are DOM-based

No E2E test changes needed. The rendered HTML is identical regardless of store vs rune implementation. Only the JavaScript execution model changes.

### Build-time verification

The Svelte compiler catches most issues: if a `.svelte.js` file has syntax errors, or if a component references an undefined variable, the build fails. Let the compiler be your safety net.
