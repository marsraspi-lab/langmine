# Proper Name Bracket Display — Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Auto-detect proper names (person names, place names) in Chinese text via jieba POS tagging, display them in [square brackets] in the transcript, and allow users to correct misclassifications.

**Architecture:** Minimal extension of existing ports/routes/frontend. `LanguageProcessor` gets `is_proper_name(token)` — Chinese implementation uses jieba `posseg`. Transcript API assigns `status="proper-name"` (skipped in content-word counting). Frontend renders with CSS `::before`/`::after` brackets and adds "Not a name" action to the word popover.

**Tech Stack:** jieba posseg (already a dependency), Python, Svelte 5

---

## Agreed Design Decisions

| Decision | Choice |
|----------|--------|
| Auto-detect or manual-only? | Auto-detect via jieba POS tagging (`nr` = person, `ns` = place) |
| Visual brackets: CSS pseudo-elements or actual chars? | CSS `::before` `"[ "` + `::after` `" ]"` — keeps token data clean |
| Classification: proper names count as content words? | No — treated like non-words (excluded from i+1 unknown count) |
| What if a word is BOTH known AND a proper name? | Known takes priority (if user marked "中国" known, don't bracket it) |
| "Not a name" action: what status does the word get? | `learning` (unknown word — if it were known, it'd already be marked) |
| Edit mechanism | Existing popover infrastructure + new API endpoint `PATCH /api/vocab/{word}` with `{"proper_name": false}` |

---

### Task 1: Add `is_proper_name` to LanguageProcessor port

**Objective:** Add abstract method `is_proper_name(token: str) -> bool` to the domain port.

**Files:**
- Modify: `src/langmine/domain/ports.py` (after `is_non_word`)

**Step 1: Add abstract method**

In `LanguageProcessor` class, after `is_non_word`:

```python
    @abstractmethod
    def is_proper_name(self, token: str) -> bool:
        """True if token is a proper name (person, place, etc.).

        Proper names should be visually distinguished and excluded
        from i+1 unknown counting.
        """
```

**Step 2: Verify**
Run: `python -c "from langmine.domain.ports import LanguageProcessor; print('OK')"`

---

### Task 2: Implement `is_proper_name` in ChineseLanguageProcessor

**Objective:** Use jieba `posseg` to detect `nr` (person name) and `ns` (place name) tags.

**Files:**
- Modify: `src/langmine/languages/chinese/service.py`

**Step 1: Add POS-based proper name detection**

In `ChineseLanguageProcessor`, add after `is_non_word`:

```python
    # Proper name POS tags (jieba posseg)
    PROPER_NAME_TAGS = frozenset({
        "nr",   # person name (e.g., 曹操, 刘备)
        "ns",   # place name (e.g., 北京, 长安)
        "nrfg", # person name — given name
        "nrt",  # person name — transliterated
    })

    def is_proper_name(self, token: str) -> bool:
        """Detect proper names via jieba POS tagging."""
        import jieba.posseg as pseg
        for word, flag in pseg.cut(token):
            if word == token and flag in self.PROPER_NAME_TAGS:
                return True
        return False
```

**Step 2: Write test**
Create test in `tests/test_chinese_processor.py` (or add to existing):

```python
def test_is_proper_name_detects_person():
    from langmine.languages.chinese.service import ChineseLanguageProcessor
    from langmine.domain.ports import Dictionary, Translator, FrequencySource

    class FakeDict(Dictionary):
        def lookup(self, word): return {"definition_de": "test", "definition_en": "test"}
    class FakeTrans(Translator):
        def translate(self, text): return "test"
    class FakeFreq(FrequencySource):
        def get_frequency(self, word): return 1000

    proc = ChineseLanguageProcessor(FakeDict(), FakeTrans(), FakeFreq())
    assert proc.is_proper_name("曹操") == True

def test_is_proper_name_rejects_common_word():
    proc = ChineseLanguageProcessor(...)
    assert proc.is_proper_name("学习") == False
```

**Step 3: Run test**

`pytest tests/ -k "proper_name" -v`

---

### Task 3: Update Transcript API to assign proper-name status

**Objective:** In the transcript preview endpoint, check `is_proper_name` and assign `status="proper-name"` (excluded from content-word counting).

**Files:**
- Modify: `src/langmine/web/routes.py` (transcript endpoint ~line 195-211)

**Step 1: Add proper-name check to token classification**

Change the token classification block in `get_video_transcript()`:

```python
for token in tokens:
    if processor.is_non_word(token):
        status = "non-word"
    elif processor.is_proper_name(token):
        status = "proper-name"
        # Proper names are not content words — do NOT increment counters
    elif token in known_words:
        status = "known"
        total_content_words += 1
        total_known_words += 1
    else:
        status = "learning"
        total_content_words += 1
        sentence_unknown += 1
    words.append({"token": token, "status": status})
```

**Step 2: Also update the preview endpoint**
Check if there's a separate preview/video endpoint using the same pattern (there's a `_get_processor()` helper).

**Step 3: Run pytest**
`pytest tests/test_web_api.py tests/test_web_transcript.py -v`

---

### Task 4: Update FakePersistence and FakeLanguageProcessor in e2e

**Objective:** All test fakes must implement `is_proper_name`.

**Files:**
- Modify: `src/langmine/web/frontend/e2e/test_server.py` (FakeLanguageProcessor)
- Modify: every `tests/test_*.py` with a FakeLanguageProcessor

**Step 1: Add to e2e test server**

```python
def is_proper_name(self, token): return False
```

**Step 2: Add to all test fakes**

Search for `class Fake.*Processor` across all test files and add the no-op method.

**Step 3: Run full pytest**
`pytest tests/ -q` — expected: all pass.

---

### Task 5: Frontend — CSS brackets + proper-name class

**Objective:** Add `.word-proper-name` CSS class with `::before`/`::after` brackets.

**Files:**
- Modify: `src/langmine/web/frontend/src/lib/TranscriptView.svelte` (CSS section)

**Step 1: Add CSS**

```css
.word-proper-name {
  color: var(--text-secondary);
  font-style: italic;
  position: relative;
}
.word-proper-name::before {
  content: "[";
  color: var(--text-secondary);
  opacity: 0.5;
}
.word-proper-name::after {
  content: "]";
  color: var(--text-secondary);
  opacity: 0.5;
}
```

Already handled: the existing `class="word-token word-{word.status}"` will apply `word-proper-name` automatically since the status is `"proper-name"`.

**Step 2: Build frontend**
```bash
cd src/langmine/web/frontend && npm run build
```

---

### Task 6: Frontend — "Not a name" action in word popover

**Objective:** When user clicks a bracketed word, the popover includes "❌ Not a proper name" button that reclassifies it as `learning`.

**Files:**
- Modify: `src/langmine/web/frontend/src/lib/TranscriptView.svelte` (popover section)
- Modify: `src/langmine/web/frontend/src/lib/api.js` (add `dismissProperName` API call)

**Step 1: Add API function in api.js**

```javascript
export async function dismissProperName(word) {
  const res = await fetch(`/api/vocab/${encodeURIComponent(word)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ proper_name: false }),
  });
  if (!res.ok) {
    const data = await res.json();
    throw new Error(data.error || 'Failed to dismiss proper name');
  }
  return res.json();
}
```

**Step 2: Add "Not a name" button in popover**

In `TranscriptView.svelte`, inside the popover actions, add after the existing status buttons:

```svelte
{#if activeWord.word.status === 'proper-name'}
  <button
    class="popover-btn"
    onclick={() => dismissProperName(activeWord.word.token).then(() => { loadTranscript(); closePopover(); addToast(`"${activeWord.word.token}" is not a proper name`, 'success'); })}
  >
    ❌ Not a proper name
  </button>
{/if}
```

Also add the `dismissProperName` import.

**Step 3: Add badge for proper-name status in popover**

In `.popover-status-row`, ensure proper-name shows correctly:

```svelte
Status: <span class="status-badge-inline word-{activeWord.word.status}">{activeWord.word.status}</span>
```

And add CSS:

```css
.status-badge-inline.word-proper-name { background: rgba(158, 158, 158, 0.15); color: #9e9e9e; }
```

**Step 4: Build frontend**
```bash
cd src/langmine/web/frontend && npm run build
```

---

### Task 7: Backend — PATCH /api/vocab/{word} proper_name=false handler

**Objective:** Add backend route that handles `{"proper_name": false}` — marks word as `learning` so brackets disappear and word counts as unknown.

**Files:**
- Modify: `src/langmine/web/routes.py` (vocab PATCH handler)

**Step 1: Add handler in existing vocab PATCH route**

In the `patch_vocab_word` handler (~line 540-570), add:

```python
elif data.get("proper_name") is False:
    # User says this is NOT a proper name → mark as learning
    persistence.mark_word_learning(word)
    _log_event(persistence, "vocab", 0, "dismissed_proper_name",
              old_value="proper-name", new_value="learning")
```

The existing route handler already accepts JSON body with various fields — just add this branch.

**Step 2: Run pytest**

`pytest tests/ -q` — verify all pass.

---

### Task 8: Integration test — full proper name flow

**Objective:** Write a test that verifies the full flow: jieba detects 曹操 as proper name → transcript shows `status="proper-name"` → dismissing → becomes `learning`.

**Files:**
- Create/Modify: `tests/test_web_api.py` (add test)

**Step 1: Write integration test**

```python
def test_transcript_shows_proper_names_as_proper_name():
    """Proper names detected by jieba appear with status=proper-name in transcript."""
    # ... setup with FakeTranscript returning text containing 曹操
    # ... call transcript API
    # ... assert 曹操 has status "proper-name"
```

**Step 2: Run**
`pytest tests/ -k "proper_name" -v`

---

### Task 9: Build + E2E

**Objective:** Build frontend, install Playwright deps, run E2E tests.

**Step 1: Build**
```bash
cd src/langmine/web/frontend && npm run build
```

**Step 2: Install browser deps if needed**
```bash
apt-get install -y libnspr4 libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libdbus-1-3 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2t64
npx playwright install chromium
```

**Step 3: Start test server + run E2E**
```bash
python src/langmine/web/frontend/e2e/test_server.py &
# wait for startup
npx playwright test
```

---

### Task 10: Commit

```bash
git add -A
git commit -m "feat: proper name bracket display with [square brackets] and editability"
```
