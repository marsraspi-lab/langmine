# Subtitle Discovery & Selection — Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Show subtitle availability immediately when a user pastes a YouTube URL, let them pick from available languages, distinguish auto-generated from manual subtitles, and use that information for better error messages and smarter merge parameters.

**Architecture:** New `TranscriptSource.list_subtitles()` port method, yt-dlp `--list-subs` adapter implementation, a lightweight `/api/videos/subtitles` endpoint, and a subtitle chip + language selector in the mine form. Subtitle kind (auto/manual) is persisted with the video and used to tune sentence merging.

**Tech Stack:** Python (Flask, yt-dlp subprocess, dataclasses), Svelte 5 (runes), existing hexagonal ports/adapters pattern.

---

## Agreed Design Decisions

| Decision | Choice |
|----------|--------|
| Pre-check trigger | On URL input change, debounced 800ms |
| UI position | Chip below the URL input, above the file upload label |
| Language selector | Dropdown replacing the chip when >1 language available |
| Auto vs manual merge gap | Auto: 700ms, Manual: 300ms, default: 500ms |
| Persist sub info? | Yes — `subtitle_language` and `subtitle_kind` fields on Video |
| `--list-subs` caching | No — call is fast (~2s), a cache adds complexity for little gain |
| Error: subs exist but fetch fails | "This video has {kind} subtitles in {lang} but download failed. Try again." |
| Error: no subs at all | "This video has no subtitles in any language." |

---

## Milestone 25: Subtitle Discovery (pre-check + UI chip + richer errors)

**User-visible outcome:** Paste a YouTube URL, see immediately whether subtitles exist, what kind, and how many languages. If no subtitles, you know before clicking Mine. If mining fails, error messages reference the subtitle info.

### Task 1: Add `SubtitleInfo` value object to ports

**Files:**
- Modify: `src/langmine/domain/ports.py`

```python
@dataclass
class SubtitleInfo:
    """Info about an available subtitle track."""
    language_code: str       # e.g. "zh-Hans", "en"
    language_name: str       # e.g. "Chinese (Simplified)", "English"
    kind: str                # "manual" or "auto"
```

### Task 2: Add `list_subtitles` to `TranscriptSource` port

**Files:**
- Modify: `src/langmine/domain/ports.py`

```python
class TranscriptSource(ABC):
    @abstractmethod
    def fetch(self, video_id: str) -> list[TranscriptChunk]: ...

    @abstractmethod
    def list_subtitles(self, video_id: str) -> list[SubtitleInfo]:
        """Return available subtitle tracks for a video.

        Returns empty list if no subtitles exist.
        Raises ValueError if the video is unavailable/private.
        """
```

### Task 3: Update all `TranscriptSource` implementations to satisfy the new abstract method

**Files:**
- Modify: `src/langmine/adapters/youtube_transcript.py`
- Modify: `src/langmine/adapters/inline_transcript.py`
- Modify: `tests/test_ports.py` (FakeTranscriptSource)

**InlineTranscript:** Returns empty list (uploaded files have no sub tracks to list).

**YouTubeTranscriptAdapter:** Runs `yt-dlp --list-subs --skip-download <url>`, parses output.

```python
def list_subtitles(self, video_id: str) -> list[SubtitleInfo]:
    """List available subtitle tracks via yt-dlp --list-subs."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    cmd = ["yt-dlp", "--list-subs", "--skip-download", "--no-playlist", "--no-warnings"]
    if self._user_agent:
        cmd.insert(1, "--user-agent")
        cmd.insert(2, self._user_agent)
    cmd.append(url)

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    stderr = result.stderr.lower() if result.stderr else ""

    if result.returncode != 0:
        if "video unavailable" in stderr or "private video" in stderr:
            raise ValueError(f"Video '{video_id}' is unavailable or private.")
        return []  # Unknown error, treat as no subtitles

    return _parse_list_subs_output(result.stdout)
```

### Task 4: Parse `yt-dlp --list-subs` output

**Files:**
- Modify: `src/langmine/transcript.py` (add `_parse_list_subs_output`)

yt-dlp `--list-subs` output looks like:

```
[info] Available subtitles for abc123:
Language Name                  Formats
zh-Hans  Chinese (Simplified)  vtt, srt, ttml
en       English               vtt, srt, ttml
zh-Hant  Chinese (Traditional) vtt, srt, ttml (auto-generated)
```

```python
def _parse_list_subs_output(output: str) -> list[SubtitleInfo]:
    """Parse yt-dlp --list-subs output into SubtitleInfo objects."""
    from langmine.domain.ports import SubtitleInfo
    import re

    subtitles = []
    in_table = False

    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        if "Available subtitles" in line or "Language" in line:
            in_table = True
            continue
        if "Has automatic captions" in line or "Available automatic" in line:
            continue
        if not in_table:
            continue

        # Parse: "zh-Hans  Chinese (Simplified)  vtt, srt, ttml (auto-generated)"
        # or:    "zh-Hans  Chinese (Simplified)  vtt, srt, ttml"
        match = re.match(
            r"^(\S+)\s{2,}(.+?)\s{2,}(vtt|srt|ttml|ass)(.*)$",
            line
        )
        if not match:
            continue

        lang_code = match.group(1)
        lang_name = match.group(2).strip()
        kind = "auto" if "auto-generated" in match.group(4).lower() else "manual"

        subtitles.append(SubtitleInfo(
            language_code=lang_code,
            language_name=lang_name,
            kind=kind,
        ))

    return subtitles
```

**Step 1: Write tests**

- Test parsing real `--list-subs` output with manual + auto subs
- Test parsing header-only output (no subs)
- Test parsing output for a video with only auto-generated subs

### Task 5: Add `GET /api/videos/subtitles` endpoint

**Files:**
- Modify: `src/langmine/web/routes.py`

```python
@app.route("/api/videos/subtitles")
def list_subtitles():
    """List available subtitle tracks for a YouTube video."""
    url = request.args.get("url", "").strip()
    if not url:
        return jsonify({"error": "Missing 'url' parameter"}), 400

    from langmine.transcript import _extract_video_id
    try:
        video_id = _extract_video_id(url)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    transcript_source = _get_transcript_source()
    if transcript_source is None:
        return jsonify({"subtitles": [], "available": False}), 200

    try:
        subs = transcript_source.list_subtitles(video_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        return jsonify({"subtitles": [], "available": False}), 200

    return jsonify({
        "subtitles": [
            {"language_code": s.language_code, "language_name": s.language_name, "kind": s.kind}
            for s in subs
        ],
        "available": len(subs) > 0,
    })
```

### Task 6: Add `fetchSubtitleInfo` to frontend API

**Files:**
- Modify: `src/langmine/web/frontend/src/lib/api.js`

```js
fetchSubtitleInfo: async (url) => {
  const res = await fetch(`/api/videos/subtitles?url=${encodeURIComponent(url)}`);
  return { ok: res.ok, status: res.status, data: await res.json() };
},
```

### Task 7: Add subtitle chip to Sidebar mine form

**Files:**
- Modify: `src/langmine/web/frontend/src/lib/Sidebar.svelte`

**State:**
```js
let subInfo = $state(null);     // {available, subtitles: [...]}
let subLoading = $state(false);
let subCheckTimer = null;
```

**On URL input change (debounced 800ms):**
```js
function handleUrlInput() {
  subInfo = null;  // clear on new input
  clearTimeout(subCheckTimer);
  const url = urlInput.trim();
  if (!url || url.length < 20) return;  // too short to be a valid URL

  subCheckTimer = setTimeout(async () => {
    subLoading = true;
    try {
      const result = await api.fetchSubtitleInfo(url);
      if (result.ok) {
        subInfo = result.data;
      }
    } catch (e) {
      // ignore — pre-check is best-effort
    } finally {
      subLoading = false;
    }
  }, 800);
}
```

**Chip UI** (below the URL input, above the file upload label):

```svelte
{#if subLoading}
  <div class="subtitle-chip loading">⏳ Checking subtitles…</div>
{:else if subInfo && subInfo.available}
  {#if subInfo.subtitles.length === 1}
    {@const s = subInfo.subtitles[0]}
    <div class="subtitle-chip {s.kind}" title="{s.language_name}">
      {s.kind === 'manual' ? '✅' : '⚠️'} {s.language_name} ({s.kind === 'manual' ? 'manual' : 'auto-generated'})
    </div>
  {:else}
    <div class="subtitle-chip manual">
      ✅ {subInfo.subtitles.length} subtitle languages available
    </div>
  {/if}
{:else if subInfo && !subInfo.available}
  <div class="subtitle-chip none">❌ No subtitles available</div>
{/if}
```

**CSS:**
```css
.subtitle-chip {
  font-size: 0.75rem;
  padding: 4px 8px;
  border-radius: 4px;
  margin-bottom: 8px;
}
.subtitle-chip.manual { background: rgba(76, 175, 80, 0.15); color: #66bb6a; }
.subtitle-chip.auto  { background: rgba(255, 152, 0, 0.15); color: #ffa726; }
.subtitle-chip.none  { background: rgba(244, 67, 54, 0.15); color: #ef5350; }
.subtitle-chip.loading { background: rgba(255,255,255,0.05); color: var(--text-secondary); }
```

### Task 8: Richer mine error messages using subtitle info

**Files:**
- Modify: `src/langmine/web/routes.py` (the `_do_mine` function in SSE path)

When the mine pipeline raises `MineError(stage="transcript")`, check if we have subtitle info and produce a better message:

```python
# In _do_mine, after catching MineError:
except MineError as e:
    msg = str(e)
    if e.stage == "transcript":
        # Enrich with subtitle info if available
        subs = transcript_source.list_subtitles(video_id)
        if subs:
            # Subs exist but fetch failed
            langs = ", ".join(f"{s.language_name} ({s.kind})" for s in subs[:3])
            msg = f"This video has subtitles ({langs}) but download failed. Try again."
        else:
            msg = "This video has no subtitles in any language."
    progress_queue.put(("error", {"message": msg, "stage": e.stage}))
```

### Task 9: End-to-end Playwright test

**Files:**
- Modify: `src/langmine/web/frontend/e2e/app.spec.js`

Test that pasting a URL shows the subtitle chip:

```js
test('subtitle chip shows on URL input', async ({ page }) => {
  const main = new AppPage(page);
  await main.goto();

  // Type a valid YouTube URL
  await main.urlInput.fill('https://www.youtube.com/watch?v=jNQXAC9IVRw');
  await page.waitForTimeout(1000);  // debounce + API call

  // Chip should appear (we can't control yt-dlp output in E2E — this test
  // verifies the UI wiring)
  const chip = page.locator('.subtitle-chip');
  await expect(chip).toBeVisible();
});
```

---

## Milestone 26: Language Selection + Kind-Aware Merge + Persist

**User-visible outcome:** When a video has multiple subtitle languages, pick which one to mine. Subtitle kind (auto/manual) stored per video and shown in the video list. Auto-generated subs get wider merge gaps for better sentence segmentation.

### Task 10: Add subtitle fields to Video model + persistence

**Files:**
- Modify: `src/langmine/domain/models.py`

```python
@dataclass
class Video:
    id: int | None
    youtube_id: str
    title: str
    language_code: str = ""
    subtitle_language: str = ""   # NEW: e.g. "zh-Hans"
    subtitle_kind: str = ""       # NEW: "manual" or "auto" or ""
```

**Files:**
- Modify: `src/langmine/adapters/sqlite_persistence.py`

Add migration for `subtitle_language TEXT DEFAULT ''` and `subtitle_kind TEXT DEFAULT ''` columns on the `videos` table. Update `save_video` / `get_video` / `list_videos` to read/write these fields.

### Task 11: Add language selector to mine form

**Files:**
- Modify: `src/langmine/web/frontend/src/lib/Sidebar.svelte`

When `subInfo.subtitles.length > 1`, replace the chip with a `<select>` dropdown:

```svelte
{#if subInfo.subtitles.length > 1}
  <div class="subtitle-chip manual" style="display:flex;align-items:center;gap:6px">
    <span>✅</span>
    <select bind:value={selectedSubLang} class="sub-lang-select">
      {#each subInfo.subtitles as s}
        <option value={s.language_code}>
          {s.language_name} ({s.kind === 'manual' ? 'manual' : 'auto'})
        </option>
      {/each}
    </select>
  </div>
{/if}
```

Add `let selectedSubLang = $state('')` state, initialized to the first subtitle when `subInfo` loads.

### Task 12: Pass selected language to mine API

**Files:**
- Modify: `src/langmine/web/frontend/src/lib/api.js` — `mineVideoStream` takes optional `language` param
- Modify: `src/langmine/web/frontend/src/lib/stores.js` — `mineVideo` passes it through
- Modify: `src/langmine/web/frontend/src/lib/Sidebar.svelte` — `handleMine` includes `selectedSubLang`

```js
// api.js
mineVideoStream: async function* (url, file = null, language = '') {
  // ... append language to body or formData
  if (language) {
    if (file) formData.append('language', language);
    else body = JSON.stringify({ url, language });
  }
}
```

### Task 13: Backend uses selected language + persists sub info

**Files:**
- Modify: `src/langmine/web/routes.py` — `mine_video`

Parse `language` from request, pass it to `YouTubeTranscriptAdapter(language_codes=[language])`. After mining, update the Video with `subtitle_language` and `subtitle_kind`.

```python
# In _do_mine:
language = request.form.get("language") or data.get("language", "")
if language:
    from langmine.adapters import YouTubeTranscriptAdapter
    transcript = YouTubeTranscriptAdapter(
        user_agent=config.user_agent,
        language_codes=[language],
    )
```

After successful mining:
```python
video = persistence.get_video(video_id)
if video and language:
    # Find the matching SubtitleInfo to get kind
    subs = transcript_source.list_subtitles(video_id)
    match = next((s for s in subs if s.language_code == language), None)
    video.subtitle_language = language
    video.subtitle_kind = match.kind if match else ""
    persistence.save_video(video)
```

### Task 14: Kind-aware merge gap in pipeline

**Files:**
- Modify: `src/langmine/pipeline.py` — `process_video`

Accept optional `subtitle_kind` parameter (default `""`). Use it to override gap:

```python
def process_video(..., subtitle_kind: str = "") -> dict:
    # ...
    if gap_ms is None:
        if subtitle_kind == "auto":
            gap_ms = 700   # auto-generated subs have no punctuation cues
        elif subtitle_kind == "manual":
            gap_ms = 300   # manual subs are well-punctuated
        else:
            gap_ms = config.sentence_gap_ms  # default 500
```

### Task 15: Show subtitle kind in video list

**Files:**
- Modify: `src/langmine/web/routes.py` — `_video_with_counts` helper
- Modify: `src/langmine/web/frontend/src/lib/Sidebar.svelte` — video list items

Add `subtitle_language` and `subtitle_kind` to the video list API response. Show a small badge in the video row:

```svelte
{#if video.subtitle_kind === 'auto'}
  <span class="sub-badge auto">🤖 auto</span>
{:else if video.subtitle_kind === 'manual'}
  <span class="sub-badge manual">✍️ manual</span>
{/if}
```

### Task 16: Integration tests

- Test full flow: URL input → subtitle chip → language select → mine with selected language
- Test that kind-aware gap produces correct merge for auto vs manual subs
- Test that subtitle info is persisted and displayed in video list

---

## Implementation Order

1. **M25 Tasks 1–9** — subtitle discovery + chip + richer errors (shippable)
2. **M26 Tasks 10–16** — language selection + kind-aware merge + persist (shippable)

Each milestone delivers a complete, user-visible feature.
