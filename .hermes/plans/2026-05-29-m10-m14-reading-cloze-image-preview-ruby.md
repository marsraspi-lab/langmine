# M10–M14: Reading, Cloze, Image Search, Preview, Ruby

> **For Hermes:** Execute each milestone as a feature branch + PR. TDD. Vertical slices.

**Goal:** Five shippable milestones that make LangMine a proper comprehensible-input tool.

**Architecture:** Each milestone is a vertical slice — user-visible from day one. No backend-first, no pipeline-first. Frontend + backend + tests in each milestone.

**Branch naming:** `feat/m10-reading-mode`, `feat/m11-cloze-export`, `feat/m12-image-search`, `feat/m13-difficulty-preview`, `feat/m14-ruby-annotations`

---

## Agreed Design Decisions

From the grilling session:

| Decision | Choice |
|----------|--------|
| Reading view shows deleted sentences? | Yes — full transcript for context |
| Word popup component | Duplicated (not shared) — ~40 lines, different positioning |
| Popup example sentences | Deferred to M14 (VocabPage deep-dive) |
| Cloze + basic export together? | Exclusive toggle — basic OR cloze, not both |
| Cloze hint source | Screenshot (M11); image search added in M12 |
| Difficulty preview trigger | Manual button only — no auto-fire |
| Preview transcript content | Read-only with known/learning/unknown highlighting |
| Ruby display + editing | Single milestone (M14) — display without editing is frustrating |
| Ruby tone colors | Pleco convention: 1st=red, 2nd=green, 3rd=blue, 4th=purple, 5th=gray |
| Keyboard shortcuts legend | Fixed bottom bar, toggled with `?` |
| Keyboard bindings | T=toggle translate, S/Space=replay, J/↓/→=next, K/↑/←=prev, Esc=close popup, ?=legend |
| Image search scope | Top-5 grid, target-language query, user picks best |

---

## M10: Reading Mode + Keyboard Shortcuts

**User outcome:** Select a video, click "📖 Read" tab → full transcript as continuous text. Click any word for popup (HSK level, frequency rank, Mark known/learning/unknown). T=toggle translation, S/Space=replay audio, arrows=nav, ?=shortcuts legend.

### Task 1: Add `GET /api/videos/<id>/transcript` endpoint

**Objective:** Return all sentences in time-order with full metadata.

**Files:**
- Modify: `src/langmine/web/routes.py`
- Create: `tests/test_web_transcript.py`

**Step 1: Write failing test**

```python
def test_transcript_endpoint_returns_ordered_sentences(client, seeded_db):
    """Transcript endpoint returns sentences sorted by start_ms."""
    resp = client.get("/api/videos/1/transcript")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "sentences" in data
    assert len(data["sentences"]) > 0
    starts = [s["start_ms"] for s in data["sentences"]]
    assert starts == sorted(starts)
```

**Step 2: Add endpoint in routes.py**

```python
@app.route("/api/videos/<int:video_id>/transcript")
def get_transcript(video_id: int):
    """Return all sentences in time-order for the reading view."""
    persistence = _get_persistence()
    sentences = persistence.get_sentences_by_video(video_id)
    sentences.sort(key=lambda s: s.start_ms)
    return jsonify({
        "video_id": video_id,
        "sentences": [_sentence_to_dict(s, persistence) for s in sentences],
    })
```

**Step 3: Run test, commit**

```bash
cd /root/projects/langmine && python -m pytest tests/test_web_transcript.py -v
git add tests/test_web_transcript.py src/langmine/web/routes.py
git commit -m "feat: add GET /api/videos/:id/transcript endpoint"
```

---

### Task 2: Create `TranscriptView.svelte` component

**Objective:** Continuous scrollable reading view with word highlighting, popup dictionary, audio playback, and keyboard shortcuts.

**Files:**
- Create: `src/langmine/web/frontend/src/lib/TranscriptView.svelte`

**Step 1: Write component**

```svelte
<script>
  import { onMount } from 'svelte';
  import { updateVocabWord } from './api.js';
  import { addToast } from './stores.js';

  let { videoId } = $props();

  let sentences = $state([]);
  let loading = $state(true);
  let showTranslation = $state(false);
  let showLegend = $state(false);
  let activeWord = $state(null);
  let activeSentenceIdx = $state(0);

  onMount(loadTranscript);

  async function loadTranscript() {
    loading = true;
    try {
      const res = await fetch(`/api/videos/${videoId}/transcript`);
      const data = await res.json();
      sentences = data.sentences || [];
    } catch (err) {
      addToast('Failed to load transcript', 'error');
    } finally {
      loading = false;
    }
  }

  function playAudio(sentence) {
    if (!sentence.has_audio) return;
    new Audio(`/api/sentences/${sentence.id}/audio`).play();
  }

  function handleWordClick(word, idx, sentenceIdx, e) {
    e.stopPropagation();
    if (activeWord?.sentenceIdx === sentenceIdx && activeWord?.idx === idx) {
      activeWord = null;
    } else {
      activeWord = { word, idx, sentenceIdx };
    }
  }

  async function setWordStatus(token, newStatus) {
    try {
      await updateVocabWord(token, newStatus);
      if (activeWord) activeWord.word.status = newStatus;
      await loadTranscript();
      addToast(`"${token}" → ${newStatus}`, 'success');
    } catch (err) {
      addToast(`Failed: ${err.message}`, 'error');
    }
  }

  function navigate(dir) {
    const next = activeSentenceIdx + dir;
    if (next >= 0 && next < sentences.length) {
      activeSentenceIdx = next;
      document.getElementById(`s-${next}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }

  function handleKeydown(e) {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
    switch (e.key) {
      case 't': case 'T': showTranslation = !showTranslation; break;
      case 's': case 'S': case ' ':
        e.preventDefault();
        if (sentences[activeSentenceIdx]) playAudio(sentences[activeSentenceIdx]);
        break;
      case 'j': case 'J': case 'ArrowDown': case 'ArrowRight': navigate(1); break;
      case 'k': case 'K': case 'ArrowUp': case 'ArrowLeft': navigate(-1); break;
      case 'Escape': activeWord = null; showLegend = false; break;
      case '?': showLegend = !showLegend; e.preventDefault(); break;
    }
  }

  function closePopover() { activeWord = null; }
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="transcript-view">
  <div class="transcript-toolbar">
    <span class="toolbar-info">{sentences.length} sentences</span>
    <div class="toolbar-actions">
      <button class="toolbar-btn" class:active={showTranslation}
        onclick={() => showTranslation = !showTranslation} title="Toggle translation (T)">
        {showTranslation ? '📖 Hide translation' : '📖 Show translation'}
      </button>
    </div>
  </div>

  {#if loading}
    <div class="loading-state">⏳ Loading transcript...</div>
  {:else if sentences.length === 0}
    <div class="empty-state">No sentences for this video yet.</div>
  {:else}
    <div class="sentence-list">
      {#each sentences as sentence, idx}
        <div id="s-{idx}" class="transcript-sentence" class:active={idx === activeSentenceIdx}
          onclick={() => activeSentenceIdx = idx} role="button" tabindex="0">
          <span class="sentence-num">{idx + 1}</span>
          <div class="sentence-content">
            <div class="sentence-chinese">
              {#if sentence.words?.length}
                {#each sentence.words as word, widx}
                  <span class="word-token word-{word.status}"
                    onclick={(e) => handleWordClick(word, widx, idx, e)}
                    role="button" tabindex="0">{word.token}</span>
                {/each}
              {:else}
                {sentence.text}
              {/if}
              {#if sentence.has_audio}
                <button class="play-btn" onclick={(e) => { e.stopPropagation(); playAudio(sentence); }}
                  title="Replay (S/Space)">▶</button>
              {/if}
            </div>
            {#if sentence.pinyin}
              <div class="sentence-pinyin">{sentence.pinyin}</div>
            {/if}
            {#if showTranslation && sentence.translation_de}
              <div class="sentence-translation">{sentence.translation_de}</div>
            {/if}
            {#if sentence.unknown_word && sentence.frequency_badge}
              <span class="freq-tag">{sentence.frequency_badge} {sentence.unknown_word} #{sentence.unknown_word_rank}</span>
            {/if}
            <span class="sentence-status status-{sentence.status}">{sentence.status}</span>
          </div>
        </div>
      {/each}
    </div>
  {/if}

  <!-- Word popover -->
  {#if activeWord}
    <div class="word-popover-overlay" onclick={closePopover}></div>
    <div class="word-popover">
      <div class="popover-word">{activeWord.word.token}</div>
      <div class="popover-meta">
        {#if activeWord.word.hsk_level}
          <span class="hsk-badge hsk-{activeWord.word.hsk_level}">HSK{activeWord.word.hsk_level}</span>
        {/if}
        {#if activeWord.word.frequency_rank}
          <span class="freq-badge">#{activeWord.word.frequency_rank}</span>
        {/if}
      </div>
      <div class="popover-status-row">
        Status: <span class="status-badge-inline word-{activeWord.word.status}">{activeWord.word.status}</span>
      </div>
      <div class="popover-actions">
        <button class="popover-btn" onclick={() => setWordStatus(activeWord.word.token, 'known')}
          disabled={activeWord.word.status === 'known'}>✅ Mark known</button>
        <button class="popover-btn" onclick={() => setWordStatus(activeWord.word.token, 'learning')}
          disabled={activeWord.word.status === 'learning'}>📚 Mark learning</button>
        <button class="popover-btn" onclick={() => setWordStatus(activeWord.word.token, 'unknown')}
          disabled={activeWord.word.status === 'unknown'}>❓ Mark unknown</button>
      </div>
      <button class="popover-close" onclick={closePopover}>✕</button>
    </div>
  {/if}

  <!-- Shortcuts legend (fixed bottom bar) -->
  {#if showLegend}
    <div class="shortcuts-bar">
      <span><kbd>T</kbd> Translate</span>
      <span><kbd>S</kbd> / <kbd>Space</kbd> Replay</span>
      <span><kbd>↓→J</kbd> Next</span>
      <span><kbd>↑←K</kbd> Previous</span>
      <span><kbd>Esc</kbd> Close</span>
      <span><kbd>?</kbd> Legend</span>
      <button class="shortcuts-close" onclick={() => showLegend = false}>✕</button>
    </div>
  {/if}
</div>

<style>
  /* ... full CSS as in original plan, plus shortcuts bar styles ... */
  .shortcuts-bar {
    position: fixed;
    bottom: 0;
    left: 320px; /* sidebar width */
    right: 0;
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 8px 24px;
    background: var(--bg-sidebar);
    border-top: 1px solid var(--border);
    font-size: 0.75rem;
    color: var(--text-secondary);
    z-index: 50;
  }
  .shortcuts-bar kbd {
    padding: 1px 5px;
    border: 1px solid var(--border);
    border-radius: 3px;
    font-family: monospace;
    font-size: 0.7rem;
    background: rgba(255,255,255,0.05);
  }
  .shortcuts-close {
    margin-left: auto;
    background: none;
    border: none;
    color: var(--text-secondary);
    cursor: pointer;
  }
</style>
```

**Step 2: Build and verify**

```bash
cd /root/projects/langmine/src/langmine/web/frontend && npm run build
# Expected: no errors
```

**Step 3: Commit**

```bash
git add src/langmine/web/frontend/src/lib/TranscriptView.svelte
git commit -m "feat: add TranscriptView with keyboard shortcuts and word popup"
```

---

### Task 3: Wire into CardList + App

**Objective:** Add "📖 Read" tab and integrate TranscriptView.

**Files:**
- Modify: `src/langmine/web/frontend/src/lib/stores.js` (add `readingMode` store)
- Modify: `src/langmine/web/frontend/src/lib/CardList.svelte` (add tab + conditional render)
- Modify: `src/langmine/web/frontend/src/App.svelte` (no changes — CardList handles the toggle)

**Step 1: Add `readingMode` store**

```javascript
export const readingMode = writable(false);
```

**Step 2: Modify CardList**

```svelte
<script>
  import SentenceCard from './SentenceCard.svelte';
  import TranscriptView from './TranscriptView.svelte';
  import { sentences, currentFilter, readingMode, loadSentences, keepSentence, deleteSentence, markWordKnown } from './stores.js';
  // ... existing script ...

  function toggleReadingMode() {
    readingMode.update(v => !v);
  }
</script>

<nav class="tabs">
  {#each FILTERS as { key, label }}
    <button class="tab" class:active={$currentFilter === key && !$readingMode}
      onclick={() => { readingMode.set(false); setFilter(key); }}>{label}</button>
  {/each}
  <button class="tab" class:active={$readingMode}
    onclick={toggleReadingMode}>📖 Read</button>
</nav>

<div class="cards-container">
  {#if $readingMode}
    <TranscriptView {videoId} />
  {:else if loading}
    <div class="empty-state">⏳ Loading...</div>
  {:else if $sentences.length === 0}
    <div class="empty-state">{emptyMessage}</div>
  {:else}
    {#each $sentences as sentence (sentence.id)}
      <SentenceCard {sentence} onkeep={onKeep} ondelete={onDelete} oniknowthis={onIknowthis} />
    {/each}
  {/if}
</div>
```

**Step 3: Build and verify**

```bash
cd /root/projects/langmine/src/langmine/web/frontend && npm run build
```

**Step 4: Commit**

```bash
git add src/langmine/web/frontend/src/lib/stores.js src/langmine/web/frontend/src/lib/CardList.svelte
git commit -m "feat: wire reading mode into CardList with Read tab"
```

---

### Task 4: E2E tests + full suite

```bash
cd /root/projects/langmine
python -m pytest tests/ -v --ignore=tests/e2e
# Expected: all pass
```

---

## M11: Cloze Deletion Export

**User outcome:** Export toggle: basic OR cloze. Cloze cards hide the unknown word, use screenshot as hint. No image search yet (M12).

### Task 5: Add cloze config fields

In `src/langmine/config.py`, add to `Config` dataclass:

```python
cloze_note_type: str = "LangMine Cloze"
cloze_card_css: str = field(default_factory=lambda: (
    ".card { font-family: Arial, sans-serif; font-size: 20px; }\n"
    ".chinese { font-size: 28px; margin: 20px 0; }\n"
    ".cloze { color: #e53935; font-weight: bold; }\n"
    ".pinyin { color: #2e7d32; font-style: italic; }\n"
    ".translation { font-size: 22px; }\n"
    ".hint-img { margin-top: 12px; max-width: 100%; }\n"
))
cloze_card_front_template: str = field(default_factory(lambda: (
    '<div class="chinese">{{cloze:sentence_zh}}</div>\n'
    '{{#audio}}{{audio}}{{/audio}}\n'
    '{{#screenshot}}<div class="hint-img">{{screenshot}}</div>{{/screenshot}}\n'
))
cloze_card_back_template: str = field(default_factory(lambda: (
    '<div class="chinese">{{sentence_zh}}</div>\n'
    '{{#audio}}{{audio}}{{/audio}}\n'
    '<hr id="answer">\n'
    '<div class="pinyin">{{sentence_pinyin}}</div>\n'
    '<div class="translation">{{translation_de}}</div>\n'
    '<div>🆕 {{unknown_word}}</div>\n'
    '{{#screenshot}}<div class="hint-img">{{screenshot}}</div>{{/screenshot}}\n'
))
```

Update `ALLOWED` set in `routes.py` config endpoint to include cloze fields.

### Task 6: Extend AnkiConnect adapter

Modify `src/langmine/adapters/anki_connect.py`:
- `export()` accepts `card_type="basic"` parameter
- When `card_type="cloze"`: use `isCloze=True`, cloze templates, replace unknown word with `{{c1::<word>}}` in sentence field
- Existing basic export path unchanged

### Task 7: Add cloze to API, CLI, and frontend

- `routes.py` `export_anki`: extract `card_type` from request, pass to adapter
- `cli.py` `_cmd_export`: add `--cloze` flag
- `api.js`: add `cardType` parameter to `exportAnki()`
- `Sidebar.svelte`: add "🕳️ Cloze deletion cards" checkbox, pass to exportAnki
- `stores.js`: exportAnki signature updated

---

## M12: Image Search

**User outcome:** When preparing cloze cards, search for images of the target word. Top-5 grid displayed, user picks the best one. The selected image is stored and embedded in cloze cards. Also usable from the popup dictionary (M14).

### Task 8: Add ImageSearch port

```python
class ImageSearch(ABC):
    @abstractmethod
    def search(self, query: str, count: int = 5) -> list[str]:
        """Return list of image URLs for a query."""
```

### Task 9: Add Google Custom Search adapter

New file: `src/langmine/adapters/google_image_search.py`

Uses Google Custom Search JSON API (free tier: 100 queries/day). Requires `GOOGLE_CSE_ID` and `GOOGLE_API_KEY` in config.

### Task 10: Add API endpoint + frontend picker

- `GET /api/images/search?q=<word>&lang=<target_lang>` → returns top-5 image URLs
- `POST /api/sentences/:id/cloze-image` → stores selected image URL on sentence
- Frontend: grid of 5 images, click to select, stored in `sentence.cloze_image_url`

### Task 11: Wire into cloze export

When `card_type="cloze"`, if `sentence.cloze_image_url` exists, include it in the card as the hint image (taking priority over screenshot).

---

## M13: Difficulty Preview

**User outcome:** Paste YouTube URL → click "🔍 Preview" → stats card + read-only transcript with known/learning/unknown word highlighting. Decide whether to mine.

### Task 12: Add `POST /api/videos/preview`

Returns: `{ total_sentences, i1_estimated, i0_count, known_word_pct, avg_unknown_per_sentence, sentences[] }`

`sentences[]` includes: `text, text_segmented, pinyin, translation_de, words[]` (for highlighting), but no `status` (not persisted).

### Task 13: Add preview to Sidebar

Manual "🔍 Preview" button, results shown in expandable section below URL input. Read-only transcript rendered inline.

---

## M14: Ruby Annotations + Dictionary

**User outcome:** Per-character pinyin with Pleco tone colors. Click character → inline edit pinyin/tone/meaning. VocabPage deep-dive: click word in popup → navigate to full dictionary view with all mined example sentences.

### Task 14: Add ruby data to Sentence model

New field: `ruby_json: str` — JSON array of `[{char, pinyin, tone, definition}]`. Computed via `pypinyin` during `process_video()` enrichment. Stored per-sentence so corrections persist.

### Task 15: Ruby display component

Toggle in reading view toolbar: "🎨 Ruby". When on:
- Each character rendered as `<ruby>字<rt style="color: tone-color">pinyin</rt></ruby>`
- Pleco tone colors: 1st=#E53935, 2nd=#43A047, 3rd=#1E88E5, 4th=#8E24AA, 5th=#9E9E9E

### Task 16: Ruby inline editing

Click a ruby character → small inline popover with: pinyin input, tone dropdown (1-5), meaning input. Save → PATCH `/api/sentences/:id/ruby` → updates `ruby_json` field.

### Task 17: VocabPage deep-dive from popup

Add "📋 Show in dictionary" link to word popover (both in SentenceCard and TranscriptView). Navigates to VocabPage with `?search=<word>` pre-populated, showing all mined sentences containing that word.

---

## Summary

| M | Feature | User-Visible Outcome |
|---|---------|---------------------|
| **M10** | Reading + Keyboard | Full transcript, T/S/Space/arrows/?, word popup |
| **M11** | Cloze Export | Exclusive basic/cloze toggle, screenshot hints |
| **M12** | Image Search | Top-5 grid picker, target-language query |
| **M13** | Difficulty Preview | Stats + read-only highlighted transcript before mining |
| **M14** | Ruby + Dictionary | Pleco tone colors, inline character editing, VocabPage deep-dive |
