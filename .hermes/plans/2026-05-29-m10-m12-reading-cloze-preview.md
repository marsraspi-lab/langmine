# M10–M12: Reading Mode, Cloze Export, Difficulty Preview

> **For Hermes:** Execute each milestone as a feature branch + PR. TDD. Vertical slices.

**Goal:** Three shippable milestones that make LangMine a proper comprehensible-input tool: reading mode with popup dictionary + keyboard shortcuts, cloze deletion Anki export, and video difficulty preview before mining.

**Architecture:** Each milestone is a vertical slice — user-visible from day one. No backend-first, no pipeline-first. Frontend + backend + tests in each milestone.

---

## M10: Reading Mode + Keyboard Shortcuts

**User outcome:** Select a video, click "📖 Read" tab → full transcript as continuous text. Click any word for popup (pinyin, definition, frequency). Press T to toggle translations. Press S to replay sentence audio. Press J/K to navigate sentences.

### Task 1: Add `GET /api/videos/<id>/transcript` endpoint

**Objective:** Return all sentences in time-order with full metadata for the reading view.

**Files:**
- Modify: `src/langmine/web/routes.py`

**Step 1: Write failing test**

Create `tests/test_web_transcript.py`:

```python
def test_transcript_endpoint_returns_ordered_sentences(client, seeded_db):
    """Transcript endpoint returns sentences sorted by start_ms."""
    resp = client.get(f"/api/videos/1/transcript")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "sentences" in data
    assert len(data["sentences"]) > 0
    # Must be time-ordered
    starts = [s["start_ms"] for s in data["sentences"]]
    assert starts == sorted(starts)
```

**Step 2: Run test to verify failure**

```bash
cd /root/projects/langmine && python -m pytest tests/test_web_transcript.py -v
# Expected: FAIL — 404 (route not registered)
```

**Step 3: Add endpoint**

In `routes.py`, inside `register_routes()`, before the helpers section:

```python
@app.route("/api/videos/<int:video_id>/transcript")
def get_transcript(video_id: int):
    """Return all sentences in time-order for the reading view."""
    persistence = _get_persistence()
    sentences = persistence.get_sentences_by_video(video_id)
    # Sort by start_ms for reading order
    sentences.sort(key=lambda s: s.start_ms)
    # Only show meaningful sentences (not deleted, not stashed unless explicitly wanted)
    status = request.args.get("status")
    if status:
        sentences = [s for s in sentences if s.status == status]

    return jsonify({
        "video_id": video_id,
        "sentences": [_sentence_to_dict(s, persistence) for s in sentences],
    })
```

**Step 4: Run test to verify pass**

```bash
cd /root/projects/langmine && python -m pytest tests/test_web_transcript.py -v
# Expected: PASS
```

**Step 5: Commit**

```bash
git add tests/test_web_transcript.py src/langmine/web/routes.py
git commit -m "feat: add GET /api/videos/:id/transcript endpoint for reading view"
```

---

### Task 2: Add `TranscriptView.svelte` component

**Objective:** New Svelte component that renders sentences as continuous scrollable text with inline word highlighting and popup dictionary.

**Files:**
- Create: `src/langmine/web/frontend/src/lib/TranscriptView.svelte`

**Step 1: Create the component shell**

Write the full component (skip test — UI component, tested via Playwright E2E later):

```svelte
<script>
  import { onMount } from 'svelte';
  import { updateVocabWord } from './api.js';
  import { addToast } from './stores.js';

  let { videoId } = $props();

  let sentences = $state([]);
  let loading = $state(true);
  let showTranslation = $state(false);
  let activeWord = $state(null);
  let activeSentenceIdx = $state(0);

  onMount(() => {
    loadTranscript();
  });

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
    const audio = new Audio(`/api/sentences/${sentence.id}/audio`);
    audio.play();
  }

  function handleWordClick(word, idx, sentenceIdx, e) {
    e.stopPropagation();
    if (activeWord && activeWord.sentenceIdx === sentenceIdx && activeWord.idx === idx) {
      activeWord = null;
    } else {
      activeWord = { word, idx, sentenceIdx };
    }
  }

  async function setWordStatus(token, newStatus) {
    try {
      await updateVocabWord(token, newStatus);
      // Update local state
      if (activeWord) activeWord.word.status = newStatus;
      // Refresh transcript to reflect vocab changes
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
      document.getElementById(`sentence-${next}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }

  function handleKeydown(e) {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

    switch (e.key) {
      case 't':
      case 'T':
        showTranslation = !showTranslation;
        break;
      case 's':
      case 'S':
        e.preventDefault();
        if (sentences[activeSentenceIdx]) {
          playAudio(sentences[activeSentenceIdx]);
        }
        break;
      case 'j':
      case 'J':
        navigate(1);
        break;
      case 'k':
      case 'K':
        navigate(-1);
        break;
      case 'Escape':
        activeWord = null;
        break;
    }
  }

  function closePopover() {
    activeWord = null;
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="transcript-view">
  <div class="transcript-toolbar">
    <span class="toolbar-info">{sentences.length} sentences</span>
    <div class="toolbar-actions">
      <button
        class="toolbar-btn"
        class:active={showTranslation}
        onclick={() => showTranslation = !showTranslation}
        title="Toggle translation (T)"
      >
        {showTranslation ? '📖 Hide translation' : '📖 Show translation'}
      </button>
      <span class="shortcut-hint">T: translate · S: replay · J/K: navigate · Esc: close popup</span>
    </div>
  </div>

  {#if loading}
    <div class="loading-state">⏳ Loading transcript...</div>
  {:else if sentences.length === 0}
    <div class="empty-state">No sentences for this video yet.</div>
  {:else}
    <div class="sentence-list">
      {#each sentences as sentence, idx}
        {@const words = sentence.words || []}
        <div
          id="sentence-{idx}"
          class="transcript-sentence"
          class:active={idx === activeSentenceIdx}
          onclick={() => activeSentenceIdx = idx}
          role="button"
          tabindex="0"
        >
          <span class="sentence-num">{idx + 1}</span>
          <div class="sentence-content">
            <!-- Chinese text with clickable words -->
            <div class="sentence-chinese">
              {#if words.length > 0}
                {#each words as word, widx}
                  <span
                    class="word-token word-{word.status}"
                    onclick={(e) => handleWordClick(word, widx, idx, e)}
                    role="button"
                    tabindex="0"
                  >
                    {word.token}
                  </span>
                {/each}
              {:else}
                {sentence.text}
              {/if}

              {#if sentence.has_audio}
                <button
                  class="play-btn"
                  onclick={(e) => { e.stopPropagation(); playAudio(sentence); }}
                  title="Replay audio (S)"
                >▶</button>
              {/if}
            </div>

            <!-- Pinyin -->
            {#if sentence.pinyin}
              <div class="sentence-pinyin">{sentence.pinyin}</div>
            {/if}

            <!-- Translation (togglable) -->
            {#if showTranslation && sentence.translation_de}
              <div class="sentence-translation">{sentence.translation_de}</div>
            {/if}

            <!-- Frequency badge for unknown word -->
            {#if sentence.unknown_word && sentence.frequency_badge}
              <span class="freq-tag">{sentence.frequency_badge} {sentence.unknown_word} #{sentence.unknown_word_rank}</span>
            {/if}

            <!-- Status badge -->
            <span class="sentence-status status-{sentence.status}">{sentence.status}</span>
          </div>
        </div>
      {/each}
    </div>
  {/if}

  <!-- Word popover (reused pattern from SentenceCard) -->
  {#if activeWord}
    <div class="word-popover-overlay" onclick={closePopover} role="button" tabindex="0"></div>
    <div class="word-popover" style="top: {activeWord.sentenceIdx * 120 + 80}px">
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
        <button
          class="popover-btn"
          onclick={() => setWordStatus(activeWord.word.token, 'known')}
          disabled={activeWord.word.status === 'known'}
        >✅ Mark known</button>
        <button
          class="popover-btn"
          onclick={() => setWordStatus(activeWord.word.token, 'learning')}
          disabled={activeWord.word.status === 'learning'}
        >📚 Mark learning</button>
        <button
          class="popover-btn"
          onclick={() => setWordStatus(activeWord.word.token, 'unknown')}
          disabled={activeWord.word.status === 'unknown'}
        >❓ Mark unknown</button>
      </div>
      <button class="popover-close" onclick={closePopover}>✕</button>
    </div>
  {/if}
</div>

<style>
  .transcript-view {
    display: flex;
    flex-direction: column;
    height: 100%;
    position: relative;
  }
  .transcript-toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 24px;
    border-bottom: 1px solid var(--border);
    background: var(--bg-sidebar);
    position: sticky;
    top: 0;
    z-index: 10;
  }
  .toolbar-info {
    font-size: 0.85rem;
    color: var(--text-secondary);
  }
  .toolbar-actions {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .toolbar-btn {
    padding: 5px 12px;
    background: none;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    color: var(--text-secondary);
    font-size: 0.8rem;
    cursor: pointer;
    transition: all 0.15s;
  }
  .toolbar-btn:hover {
    color: var(--text);
    border-color: var(--text-secondary);
  }
  .toolbar-btn.active {
    color: var(--accent);
    border-color: var(--accent);
    background: rgba(233, 69, 96, 0.1);
  }
  .shortcut-hint {
    font-size: 0.7rem;
    color: var(--text-secondary);
    opacity: 0.6;
  }
  .loading-state, .empty-state {
    text-align: center;
    color: var(--text-secondary);
    padding: 80px 0;
  }
  .sentence-list {
    flex: 1;
    overflow-y: auto;
    padding: 16px 24px;
  }
  .transcript-sentence {
    display: flex;
    gap: 12px;
    padding: 12px 16px;
    margin-bottom: 8px;
    border: 1px solid transparent;
    border-radius: var(--radius);
    cursor: pointer;
    transition: background 0.15s, border-color 0.15s;
  }
  .transcript-sentence:hover {
    background: rgba(255, 255, 255, 0.03);
  }
  .transcript-sentence.active {
    background: rgba(233, 69, 96, 0.08);
    border-color: rgba(233, 69, 96, 0.3);
  }
  .sentence-num {
    color: var(--text-secondary);
    font-size: 0.75rem;
    min-width: 28px;
    text-align: right;
    padding-top: 4px;
    opacity: 0.5;
  }
  .sentence-content {
    flex: 1;
    min-width: 0;
  }
  .sentence-chinese {
    font-size: 1.2rem;
    line-height: 1.8;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 2px 6px;
  }

  /* Word tokens (same style as SentenceCard) */
  .word-token {
    cursor: pointer;
    padding: 1px 4px;
    border-radius: 3px;
    transition: background 0.15s;
    user-select: none;
  }
  .word-token:hover {
    filter: brightness(1.2);
  }
  .word-known { color: var(--accent-green, #4ecca3); }
  .word-learning {
    color: #ffa726;
    border-bottom: 2px dotted #ffa726;
  }
  .word-unknown {
    color: var(--accent, #e94560);
    border-bottom: 2px dotted var(--accent, #e94560);
  }

  .play-btn {
    background: none;
    border: 1px solid var(--border);
    border-radius: 50%;
    width: 24px;
    height: 24px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    color: var(--text-secondary);
    font-size: 0.65rem;
    cursor: pointer;
    margin-left: 6px;
    flex-shrink: 0;
  }
  .play-btn:hover {
    color: var(--accent);
    border-color: var(--accent);
  }

  .sentence-pinyin {
    font-size: 0.85rem;
    color: var(--accent-green);
    font-style: italic;
    margin-top: 2px;
  }
  .sentence-translation {
    font-size: 0.9rem;
    color: var(--text-secondary);
    margin-top: 4px;
    padding-left: 8px;
    border-left: 2px solid var(--border);
  }
  .freq-tag {
    display: inline-block;
    font-size: 0.7rem;
    color: var(--text-secondary);
    margin-top: 4px;
    opacity: 0.7;
  }
  .sentence-status {
    display: inline-block;
    font-size: 0.65rem;
    padding: 1px 6px;
    border-radius: 3px;
    margin-left: 6px;
    vertical-align: middle;
    text-transform: uppercase;
  }
  .status-i1 { background: rgba(233, 69, 96, 0.2); color: var(--accent); }
  .status-i0 { background: rgba(78, 204, 163, 0.2); color: var(--accent-green); }
  .status-kept { background: rgba(78, 204, 163, 0.3); color: var(--accent-green); }
  .status-stashed { background: rgba(255, 255, 255, 0.05); color: var(--text-secondary); }
  .status-deleted { background: rgba(255, 255, 255, 0.05); color: var(--text-secondary); text-decoration: line-through; }

  /* Word popover (reused from SentenceCard pattern) */
  .word-popover-overlay {
    position: fixed;
    inset: 0;
    z-index: 90;
  }
  .word-popover {
    position: fixed;
    left: 50%;
    top: 50%;
    transform: translate(-50%, -50%);
    z-index: 100;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px 20px;
    min-width: 220px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.5);
  }
  .popover-word {
    font-size: 1.3rem;
    font-weight: 600;
    margin-bottom: 8px;
  }
  .popover-meta {
    display: flex;
    gap: 6px;
    margin-bottom: 8px;
  }
  .hsk-badge {
    padding: 1px 6px;
    border-radius: 3px;
    font-size: 0.7rem;
    font-weight: 700;
    background: rgba(100, 149, 237, 0.25);
    color: #6495ed;
  }
  .freq-badge {
    padding: 1px 6px;
    border-radius: 3px;
    font-size: 0.7rem;
    background: rgba(255, 255, 255, 0.08);
    color: var(--text-secondary);
  }
  .popover-status-row {
    font-size: 0.8rem;
    color: var(--text-secondary);
    margin-bottom: 10px;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .status-badge-inline {
    padding: 1px 8px;
    border-radius: 3px;
    font-size: 0.75rem;
    font-weight: 600;
  }
  .status-badge-inline.word-known { background: rgba(78, 204, 163, 0.2); }
  .status-badge-inline.word-learning { background: rgba(255, 167, 38, 0.2); }
  .status-badge-inline.word-unknown { background: rgba(233, 69, 96, 0.2); }
  .popover-actions {
    display: flex;
    flex-direction: column;
    gap: 5px;
  }
  .popover-btn {
    padding: 6px 12px;
    border: 1px solid var(--border);
    border-radius: 4px;
    background: transparent;
    color: var(--text);
    font-size: 0.8rem;
    cursor: pointer;
    text-align: left;
  }
  .popover-btn:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.08);
  }
  .popover-btn:disabled {
    opacity: 0.4;
    cursor: default;
  }
  .popover-close {
    position: absolute;
    top: 6px;
    right: 10px;
    background: none;
    border: none;
    color: var(--text-secondary);
    font-size: 0.9rem;
    cursor: pointer;
  }
</style>
```

**Step 2: Verify it compiles**

```bash
cd /root/projects/langmine/src/langmine/web/frontend && npm run build
# Expected: no errors
```

**Step 3: Commit**

```bash
git add src/langmine/web/frontend/src/lib/TranscriptView.svelte
git commit -m "feat: add TranscriptView component with reading mode and popup dictionary"
```

---

### Task 3: Wire TranscriptView into App.svelte with "Read" tab

**Objective:** Add a "📖 Read" tab next to the filter tabs in the curation view.

**Files:**
- Modify: `src/langmine/web/frontend/src/lib/CardList.svelte`
- Modify: `src/langmine/web/frontend/src/App.svelte`
- Modify: `src/langmine/web/frontend/src/lib/stores.js`

**Step 1: Add `readingMode` store**

In `stores.js`, add:

```javascript
/** @type {import('svelte/store').Writable<boolean>} */
export const readingMode = writable(false);
```

**Step 2: Modify CardList to toggle between card view and reading view**

In `CardList.svelte`, add import and conditional rendering:

```svelte
<script>
  import SentenceCard from './SentenceCard.svelte';
  import TranscriptView from './TranscriptView.svelte';
  import {
    sentences, currentFilter, readingMode,
    loadSentences, keepSentence, deleteSentence, markWordKnown
  } from './stores.js';
  // ... rest of existing script ...

  function toggleReadingMode() {
    readingMode.update(v => !v);
  }
</script>

<nav class="tabs">
  <!-- existing filter tabs -->
  {#each FILTERS as { key, label }}
    <button class="tab" class:active={$currentFilter === key && !$readingMode}
      onclick={() => { readingMode.set(false); setFilter(key); }}>
      {label}
    </button>
  {/each}
  <button class="tab" class:active={$readingMode}
    onclick={toggleReadingMode}>
    📖 Read
  </button>
</nav>

<div class="cards-container">
  {#if $readingMode}
    <TranscriptView {videoId} />
  {:else if loading}
    <!-- ... rest of existing card view ... -->
```

**Step 3: Build and verify**

```bash
cd /root/projects/langmine/src/langmine/web/frontend && npm run build
# Expected: no errors
```

**Step 4: Commit**

```bash
git add src/langmine/web/frontend/src/lib/CardList.svelte src/langmine/web/frontend/src/lib/stores.js
git commit -m "feat: wire reading mode into CardList with toggle tab"
```

---

### Task 4: Add Playwright E2E test for reading mode

**Objective:** Verify the reading mode loads and keyboard shortcuts work.

**Files:**
- Create: `tests/e2e/test_reading_mode.py`

**Step 1: Write the test**

```python
def test_reading_mode_loads_and_displays_sentences(page, live_server):
    """Reading mode shows sentences and keyboard T toggles translations."""
    page.goto(live_server.url)
    page.wait_for_selector("text=LangMine")

    # Click a video that has sentences
    page.click(".video-item")
    page.wait_for_selector(".tab")

    # Click Read tab
    page.click("text=📖 Read")
    page.wait_for_selector(".transcript-sentence")

    # Verify sentences are visible
    sentences = page.locator(".transcript-sentence")
    count = sentences.count()
    assert count > 0

    # Press T to show translations
    page.keyboard.press("t")
    page.wait_for_selector(".sentence-translation")

    # Press T again to hide
    page.keyboard.press("t")
    # Translation should disappear
    assert page.locator(".sentence-translation").count() == 0


def test_popup_dictionary_on_word_click(page, live_server):
    """Clicking a word opens popup with HSK badge and status controls."""
    page.goto(live_server.url)
    page.click(".video-item")
    page.wait_for_selector(".tab")
    page.click("text=📖 Read")
    page.wait_for_selector(".transcript-sentence")

    # Click first word token
    page.locator(".word-token").first.click()
    page.wait_for_selector(".word-popover")

    # Popup should show the word and action buttons
    assert page.locator(".popover-word").is_visible()
    assert page.locator("text=Mark known").is_visible()
```

**Step 2: Run tests**

```bash
# Start server first, then:
cd /root/projects/langmine && python -m pytest tests/e2e/test_reading_mode.py -v
# Expected: PASS (or adapt based on test data)
```

**Step 3: Commit**

```bash
git add tests/e2e/test_reading_mode.py
git commit -m "test: add Playwright E2E tests for reading mode"
```

---

### Task 5: Final M10 commit — run full suite

```bash
cd /root/projects/langmine
python -m pytest tests/ -v --ignore=tests/e2e
# Expected: all non-E2E tests pass
npm run build --prefix src/langmine/web/frontend
# Expected: no build errors
```

---

## M11: Cloze Deletion Export

**User outcome:** When exporting to Anki, optionally create cloze deletion cards. Cloze cards hide the unknown word with `[...]` on front, show full sentence + translation on back.

### Task 6: Add cloze note type config to config.yaml defaults

**Objective:** Add `cloze_note_type` and cloze card templates to the config model.

**Files:**
- Modify: `src/langmine/config.py`
- Modify: `tests/test_config.py`

**Step 1: Write failing test**

```python
def test_cloze_config_defaults():
    """Cloze config fields have sensible defaults."""
    from langmine.config import Config
    c = Config()
    assert c.cloze_note_type == "LangMine Cloze"
    assert "{{cloze:sentence_zh}}" in c.cloze_card_front_template
    assert "{{sentence_pinyin}}" in c.cloze_card_back_template
```

**Step 2: Run test to verify failure**

```bash
cd /root/projects/langmine && python -m pytest tests/test_config.py::test_cloze_config_defaults -v
# Expected: FAIL — AttributeError
```

**Step 3: Add fields to Config dataclass**

In `config.py`, add to the `Config` dataclass:

```python
# Cloze card fields
cloze_note_type: str = "LangMine Cloze"
cloze_card_css: str = field(default_factory=lambda: (
    ".card { font-family: Arial, sans-serif; font-size: 20px; }\n"
    ".chinese { font-size: 28px; margin: 20px 0; }\n"
    ".cloze { color: #e53935; font-weight: bold; }\n"
    ".pinyin { color: #2e7d32; font-style: italic; }\n"
    ".translation { font-size: 22px; }\n"
    ".hint { font-size: 16px; color: #888; margin-top: 12px; }\n"
))
cloze_card_front_template: str = field(default_factory=lambda: (
    '<div class="chinese">{{cloze:sentence_zh}}</div>\n'
    '{{#audio}}{{audio}}{{/audio}}\n'
))
cloze_card_back_template: str = field(default_factory=lambda: (
    '<div class="chinese">{{sentence_zh}}</div>\n'
    '{{#audio}}{{audio}}{{/audio}}\n'
    '<hr id="answer">\n'
    '<div class="pinyin">{{sentence_pinyin}}</div>\n'
    '<div class="translation">{{translation_de}}</div>\n'
    '<div class="hint">🆕 {{unknown_word}}</div>\n'
    '{{#screenshot}}<div>{{screenshot}}</div>{{/screenshot}}\n'
))
```

Also update the `ALLOWED` set in `routes.py`'s config update endpoint to include: `"cloze_note_type", "cloze_card_css", "cloze_card_front_template", "cloze_card_back_template"`.

**Step 4: Run test to verify pass**

```bash
cd /root/projects/langmine && python -m pytest tests/test_config.py::test_cloze_config_defaults -v
# Expected: PASS
```

**Step 5: Commit**

```bash
git add src/langmine/config.py tests/test_config.py
git commit -m "feat: add cloze note type config with sensible defaults"
```

---

### Task 7: Extend AnkiConnect adapter to support cloze notes

**Objective:** The `export()` method creates cloze note type if `card_type="cloze"`.

**Files:**
- Modify: `src/langmine/adapters/anki_connect.py`

**Step 1: Read current adapter to understand structure**

Read `src/langmine/adapters/anki_connect.py`. Identify the model-creation logic.

**Step 2: Add cloze model creation**

After the existing `_ensure_note_type` method, add (or extend the method to accept a `note_type_name` parameter):

```python
def _ensure_cloze_note_type(
    self,
    note_type_name: str,
    card_css: str,
    card_front: str,
    card_back: str,
    force_update: bool = False,
) -> bool:
    """Create or update the cloze note type."""
    payload = {
        "action": "findModelsByName",
        "params": {"modelNames": [note_type_name]},
    }
    existing = self._invoke_anki(payload)
    model_exists = bool(existing.get("result", []))

    if model_exists:
        if not force_update:
            return False
        # Update existing model
        self._update_cloze_model(note_type_name, card_css, card_front, card_back)
        return False

    # Create new cloze model
    create_payload = {
        "action": "createModel",
        "params": {
            "modelName": note_type_name,
            "inOrderFields": [
                "sentence_zh",
                "sentence_pinyin",
                "translation_de",
                "unknown_word",
                "audio",
                "screenshot",
            ],
            "css": card_css,
            "isCloze": True,
            "cardTemplates": [
                {
                    "Name": "Cloze Card",
                    "Front": card_front,
                    "Back": card_back,
                }
            ],
        },
    }
    create_result = self._invoke_anki(create_payload)
    if create_result.get("error"):
        raise ConnectionError(f"Failed to create cloze note type: {create_result['error']}")
    return True
```

**Step 3: Modify export() to accept card_type parameter**

Add `card_type: str = "basic"` parameter to `export()`. When `card_type="cloze"`:
- Use `cloze_note_type` string
- The sentence text field gets `{{c1::unknown_word}}` replacement for the cloze
- The `_ensure_note_type` call uses cloze-specific templates

Actually, cleaner approach: add a new method `export_cloze()` or modify `export()` with a parameter. Let's keep it simple — add `card_type` to `export()` and branch:

```python
def export(
    self,
    sentences,
    deck_name="Chinese::Sentence Mining",
    note_type_name="LangMine Sentence",
    card_css="",
    card_front="",
    card_back="",
    force_update_model=False,
    card_type="basic",
):
```

When `card_type == "cloze"`:
- Use `note_type_name` as the cloze note type
- `_ensure_cloze_note_type(...)` instead of `_ensure_note_type(...)`
- The field `sentence_zh` contains cloze-formatted text: replace `{{unknown_word}}` with `{{c1::<word>}}`

**Step 4: Commit**

```bash
git add src/langmine/adapters/anki_connect.py
git commit -m "feat: add cloze deletion note type support to AnkiConnect adapter"
```

---

### Task 8: Add cloze export to API and CLI

**Objective:** `POST /api/export/anki` accepts `card_type: "cloze"`. CLI `--cloze` flag.

**Files:**
- Modify: `src/langmine/web/routes.py` (export_anki route)
- Modify: `src/langmine/cli.py` (export command)

**Step 1: Update API route**

In `routes.py`, `export_anki()`:

```python
card_type = data.get("card_type", "basic")
# ... pass card_type to exporter.export()
result = exporter.export(
    sentences=sentences,
    deck_name=config.deck_name,
    note_type_name=config.cloze_note_type if card_type == "cloze" else config.note_type,
    card_css=config.cloze_card_css if card_type == "cloze" else config.card_css,
    card_front=config.cloze_card_front_template if card_type == "cloze" else config.card_front_template,
    card_back=config.cloze_card_back_template if card_type == "cloze" else config.card_back_template,
    force_update_model=force_update,
    card_type=card_type,
)
```

**Step 2: Update CLI**

In `cli.py`, `_cmd_export()`:

```python
@export_parser.argument("--cloze", action="store_true", help="Export as cloze deletion cards")
```

Then pass `card_type="cloze"` to the exporter when `args.cloze` is set.

**Step 3: Update frontend API helper and Sidebar**

In `api.js`:

```javascript
exportAnki: (videoId, forceUpdateModel, cardType = 'basic') =>
  post('/export/anki', {
    ...(videoId ? { video_id: videoId } : { all_kept: true }),
    force_update_model: forceUpdateModel || false,
    card_type: cardType,
  }),
```

In `Sidebar.svelte`, add a checkbox or dropdown:

```svelte
let clozeMode = $state(false);
// ...
<label class="force-update-label">
  <input type="checkbox" bind:checked={clozeMode} disabled={$exporting} />
  🕳️ Cloze deletion cards (hide unknown word)
</label>
```

And pass `clozeMode` to `exportAnki(null, forceUpdateModel, clozeMode ? 'cloze' : 'basic')`.

**Step 4: Build and verify**

```bash
cd /root/projects/langmine/src/langmine/web/frontend && npm run build
cd /root/projects/langmine && python -m pytest tests/ -v --ignore=tests/e2e
# Expected: all pass, no regressions
```

**Step 5: Commit**

```bash
git add src/langmine/web/routes.py src/langmine/cli.py src/langmine/web/frontend/src/lib/api.js src/langmine/web/frontend/src/lib/Sidebar.svelte src/langmine/web/frontend/src/lib/stores.js
git commit -m "feat: add cloze deletion export to API, CLI, and frontend"
```

---

## M12: Video Difficulty Preview

**User outcome:** Before mining, LangMine shows a preview: "% known words, estimated i+1 count, avg unfamiliar per sentence." The user decides whether to proceed.

### Task 9: Add `POST /api/videos/preview` endpoint

**Objective:** Quick classification pass — no audio download, no persistence. Returns difficulty stats.

**Files:**
- Modify: `src/langmine/web/routes.py`

**Step 1: Write failing test**

```python
def test_preview_endpoint_returns_stats(client_with_processor):
    """Preview endpoint returns difficulty stats without persisting."""
    resp = client_with_processor.post("/api/videos/preview",
        json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "total_sentences" in data
    assert "known_word_pct" in data
    assert "estimated_i1" in data
    assert "avg_unknown_per_sentence" in data
    # No video should be persisted
    list_resp = client_with_processor.get("/api/videos")
    assert len(list_resp.get_json()["videos"]) == 0  # unchanged
```

**Step 2: Run test to verify failure**

```bash
cd /root/projects/langmine && python -m pytest tests/test_web_transcript.py::test_preview_endpoint_returns_stats -v
# Expected: FAIL — 404
```

**Step 3: Add endpoint**

In `routes.py`:

```python
@app.route("/api/videos/preview", methods=["POST"])
def preview_video():
    """Quick difficulty preview without downloading audio or persisting."""
    data = request.get_json(silent=True)
    if not data or "url" not in data:
        return jsonify({"error": "Missing 'url' field"}), 400

    from langmine.transcript import _extract_video_id, merge_sentences
    from langmine.domain.classifier import SentenceClassifier

    video_id = _extract_video_id(data["url"])
    persistence = _get_persistence()
    processor = _get_processor()
    transcript = _get_transcript_source()

    if transcript is None:
        return jsonify({"error": "Transcript source not configured"}), 503

    try:
        chunks = transcript.fetch(video_id)
        merged = merge_sentences(chunks)

        if not merged:
            return jsonify({"error": "No sentences found"}), 400

        # Quick classification without persistence
        classifier = SentenceClassifier(processor, persistence)
        sentences = classifier.classify(video_id=0, sentences=merged, max_cards=999)

        # Compute stats
        i1_count = sum(1 for s in sentences if s.status == "i1")
        i0_count = sum(1 for s in sentences if s.status == "i0")
        stashed_count = sum(1 for s in sentences if s.status == "stashed")

        total_words = 0
        unknown_words = 0
        for s in sentences:
            tokens = processor.segment(s.text)
            content_words = [t for t in tokens if not processor.is_non_word(t)]
            known_words = persistence.get_known_words()
            total_words += len(content_words)
            unknown_words += sum(1 for w in content_words if w not in known_words)

        known_pct = round((1 - unknown_words / total_words) * 100) if total_words > 0 else 0
        avg_unknown = round(unknown_words / len(merged), 1) if merged else 0

        return jsonify({
            "video_id": video_id,
            "total_sentences": len(merged),
            "i1_estimated": i1_count,
            "i0_count": i0_count,
            "stashed_count": stashed_count,
            "known_word_pct": known_pct,
            "avg_unknown_per_sentence": avg_unknown,
        })

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Preview failed: {e}"}), 500
```

**Step 4: Run test to verify pass**

```bash
cd /root/projects/langmine && python -m pytest tests/test_web_transcript.py::test_preview_endpoint_returns_stats -v
# Expected: PASS (or adapt for mock transcript source)
```

**Step 5: Commit**

```bash
git add src/langmine/web/routes.py tests/test_web_transcript.py
git commit -m "feat: add POST /api/videos/preview for difficulty stats"
```

---

### Task 10: Add preview to frontend mining flow

**Objective:** When user types a URL and clicks "Preview" (or tabs away), show 2-3 stat lines before they click "Mine".

**Files:**
- Modify: `src/langmine/web/frontend/src/lib/Sidebar.svelte`
- Modify: `src/langmine/web/frontend/src/lib/api.js`

**Step 1: Add preview API call**

In `api.js`:

```javascript
previewVideo: (url) => post('/videos/preview', { url }),
```

**Step 2: Add preview state and UI in Sidebar**

In `Sidebar.svelte`, add:

```svelte
let previewData = $state(null);
let previewing = $state(false);

async function handlePreview() {
  const url = urlInput.trim();
  if (!url) return;
  previewing = true;
  previewData = null;
  try {
    const { ok, data } = await api.previewVideo(url);
    if (ok) {
      previewData = data;
    } else {
      mineStatus.set(`❌ ${data.error || 'Preview failed'}`);
    }
  } catch (err) {
    mineStatus.set(`❌ ${err.message}`);
  } finally {
    previewing = false;
  }
}
```

Add a "Preview" button next to the URL input, and a preview stats box below it:

```svelte
<div class="mine-form">
  <input ... />
  <div class="mine-buttons">
    <button onclick={handlePreview} disabled={$mining || previewing || !urlInput.trim()}>
      {previewing ? '⏳' : '🔍 Preview'}
    </button>
    <button onclick={handleMine} disabled={$mining}>
      {$mining ? '⏳' : '⛏️ Mine'}
    </button>
  </div>

  {#if previewData}
    <div class="preview-stats">
      <div class="preview-stat"><strong>{previewData.total_sentences}</strong> sentences</div>
      <div class="preview-stat"><strong>{previewData.known_word_pct}%</strong> known words</div>
      <div class="preview-stat"><strong>{previewData.estimated_i1}</strong> i+1 candidates</div>
      <div class="preview-stat"><strong>{previewData.avg_unknown_per_sentence}</strong> avg. unknown/sentence</div>
    </div>
  {/if}
  ...
</div>
```

CSS:

```css
.mine-buttons {
  display: flex;
  gap: 8px;
}
.mine-buttons button {
  flex: 1;
  padding: 8px;
  border: none;
  border-radius: var(--radius);
  font-size: 0.85rem;
  cursor: pointer;
}
.mine-buttons button:first-child {
  background: var(--bg);
  color: var(--text-secondary);
  border: 1px solid var(--border);
}
.mine-buttons button:first-child:hover:not(:disabled) {
  border-color: var(--accent);
  color: var(--text);
}
.mine-buttons button:last-child {
  background: var(--accent);
  color: white;
}
.preview-stats {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  padding: 10px;
  margin-top: 8px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}
.preview-stat {
  font-size: 0.8rem;
  color: var(--text-secondary);
}
.preview-stat strong {
  color: var(--text);
  font-size: 0.95rem;
}
```

**Step 3: Build and verify**

```bash
cd /root/projects/langmine/src/langmine/web/frontend && npm run build
# Expected: no errors
```

**Step 4: Commit**

```bash
git add src/langmine/web/frontend/src/lib/Sidebar.svelte src/langmine/web/frontend/src/lib/api.js
git commit -m "feat: add video difficulty preview to mining sidebar"
```

---

### Task 11: Final integration test + full suite

```bash
cd /root/projects/langmine
python -m pytest tests/ -v --ignore=tests/e2e
# Expected: all pass
npm run build --prefix src/langmine/web/frontend
# Expected: no build errors
```

---

## Summary

| Milestone | Feature | User-Visible Outcome |
|-----------|---------|---------------------|
| **M10** | Reading Mode + Keyboard Shortcuts | "📖 Read" tab → full transcript, T=toggle translation, S=replay audio, click word=popup dictionary |
| **M11** | Cloze Deletion Export | Export as cloze cards (hide unknown word) alongside existing sentence cards |
| **M12** | Video Difficulty Preview | "🔍 Preview" button shows % known words + estimated i+1 count before mining |

**Total new files:** 2 (TranscriptView.svelte, test_web_transcript.py)
**Files modified:** routes.py, config.py, anki_connect.py, cli.py, api.js, stores.js, CardList.svelte, Sidebar.svelte, test_config.py

**Branch naming:** `feat/m10-reading-mode`, `feat/m11-cloze-export`, `feat/m12-difficulty-preview`
