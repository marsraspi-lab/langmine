# Re-mine from Cache — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cache transcript during initial mining, then add a "re-mine" button that re-runs the full pipeline from cache without re-downloading from YouTube.

**Architecture:** Store raw transcript chunks as JSON in the existing `video.transcript_json` column during initial mining. Create a `CachedTranscriptSource` adapter that feeds cached chunks back into the pipeline. Add a `POST /api/videos/<id>/remine` SSE endpoint and a sidebar button.

**Tech Stack:** Python (Flask SSE, stdlib `json`), Svelte 5 (runes), existing pipeline/adapter patterns

---

### Task 1: Cache transcript_json during mining

**Files:**
- Modify: `src/langmine/pipeline.py:1-65` (inline fetch+merge, serialize chunks)
- Remove: `src/langmine/pipeline.py:132-144` (`_fetch_and_merge_transcript` — only caller was inlined)
- Modify: `tests/test_pipeline.py` (add test)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_pipeline.py` at end of file:

```python
import json


def test_process_video_caches_transcript_json():
    """process_video should store raw transcript chunks as JSON on the video."""
    transcript = FakeTranscript(["已知", "未知 单词"])
    audio = FakeAudio()
    persistence = FakePersistence(known_words={"已知"})
    processor = FakeChineseProcessor()

    process_video(
        transcript_source=transcript,
        audio_processor=audio,
        persistence=persistence,
        language_processor=processor,
        video_id="test_cache",
        output_dir="/tmp/test",
        config=_TEST_CONFIG,
    )

    video = persistence.get_video("test_cache")
    assert video.transcript_json, "transcript_json should not be empty"

    chunks = json.loads(video.transcript_json)
    assert len(chunks) == 2
    assert chunks[0]["text"] == "已知"
    assert chunks[0]["start_ms"] == 0
    assert chunks[1]["text"] == "未知 单词"
    assert chunks[1]["start_ms"] == 2000
```

- [ ] **Step 2: Run test to verify it fails**

```bash
source .venv/bin/activate && python -m pytest tests/test_pipeline.py::test_process_video_caches_transcript_json -v
```

Expected: FAIL — `transcript_json` is `""` (default on Video model)

- [ ] **Step 3: Implement transcript caching**

In `src/langmine/pipeline.py`, inline the fetch+merge into `process_video` so raw chunks are available for caching:

**Replace lines 60-64:**
```python
    # 1. Fetch and merge transcript
    _progress("Fetching transcript…")
    merged = _fetch_and_merge_transcript(
        transcript_source, video_id, subtitle_language, gap_ms
    )
```

**With:**
```python
    # 1. Fetch transcript — cache raw chunks before merging
    _progress("Fetching transcript…")
    raw_chunks = transcript_source.fetch(video_id, language=subtitle_language)
    merged = merge_sentences(raw_chunks, gap_ms=gap_ms)
    if not merged:
        raise MineError("No sentences could be extracted from the video.", "transcript")
    raw_json = json.dumps(
        [
            {
                "text": c.text,
                "start_ms": c.start_ms,
                "duration_ms": c.duration_ms,
            }
            for c in raw_chunks
        ]
    )
```

**Replace lines 67-72 (save video — set transcript_json):**
```python
    # 2. Save video metadata
    video = Video(
        youtube_id=video_id,
        title=video_id,  # Title fetched later (M3/M7)
        language_code=config.source_language,
    )
    persistence.save_video(video)
```

**With:**
```python
    # 2. Save video metadata
    video = Video(
        youtube_id=video_id,
        title=video_id,  # Title fetched later (M3/M7)
        language_code=config.source_language,
        transcript_json=raw_json,
    )
    persistence.save_video(video)
```

**Delete `_fetch_and_merge_transcript` function (lines 132-144):**
```python
# Remove this entire function — it's now inlined in process_video
```

- [ ] **Step 4: Run test to verify it passes**

```bash
source .venv/bin/activate && python -m pytest tests/test_pipeline.py::test_process_video_caches_transcript_json -v
```

Expected: PASS

- [ ] **Step 5: Run all pipeline tests**

```bash
source .venv/bin/activate && python -m pytest tests/test_pipeline.py -v
```

All 11 tests must pass.

- [ ] **Step 6: Commit**

```bash
git add src/langmine/pipeline.py tests/test_pipeline.py
git commit -m "feat: cache raw transcript JSON on video during mining"
```

---

### Task 2: CachedTranscriptSource adapter

**Files:**
- Create: `src/langmine/adapters/cached_transcript.py`
- Create: `tests/test_cached_transcript.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_cached_transcript.py`:

```python
"""Tests for CachedTranscriptSource."""

from langmine.adapters.cached_transcript import CachedTranscriptSource
from langmine.domain.ports import TranscriptChunk


def test_cached_transcript_returns_stored_chunks():
    """CachedTranscriptSource should return the chunks it was created with."""
    chunks = [
        TranscriptChunk(text="你好", start_ms=0, duration_ms=1000),
        TranscriptChunk(text="世界", start_ms=2000, duration_ms=1500),
    ]
    source = CachedTranscriptSource(chunks)
    result = source.fetch("any_video_id", language="")
    assert len(result) == 2
    assert result[0].text == "你好"
    assert result[0].start_ms == 0
    assert result[0].duration_ms == 1000
    assert result[1].text == "世界"
    assert result[1].start_ms == 2000
    assert result[1].duration_ms == 1500


def test_cached_transcript_ignores_language_param():
    """CachedTranscriptSource.fetch should ignore the language parameter."""
    chunks = [TranscriptChunk(text="test", start_ms=0, duration_ms=500)]
    source = CachedTranscriptSource(chunks)
    result = source.fetch("any_video_id", language="zh-Hans")
    assert result == chunks


def test_cached_transcript_list_subtitles_returns_empty():
    """CachedTranscriptSource.list_subtitles should return an empty list."""
    source = CachedTranscriptSource([])
    subs = source.list_subtitles("any_video_id")
    assert subs == []


def test_cached_transcript_empty_chunks():
    """CachedTranscriptSource with empty chunks should return empty list."""
    source = CachedTranscriptSource([])
    result = source.fetch("any_video_id", language="")
    assert result == []
```

- [ ] **Step 2: Run test to verify it fails**

```bash
source .venv/bin/activate && python -m pytest tests/test_cached_transcript.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'langmine.adapters.cached_transcript'`

- [ ] **Step 3: Write the adapter**

Create `src/langmine/adapters/cached_transcript.py`:

```python
"""TranscriptSource that returns pre-cached transcript chunks."""

from langmine.domain.ports import SubtitleInfo, TranscriptChunk, TranscriptSource


class CachedTranscriptSource(TranscriptSource):
    """Returns transcript chunks from a pre-loaded list (no network).

    Used for re-mining videos without re-downloading from YouTube.
    """

    def __init__(self, chunks: list[TranscriptChunk]):
        self._chunks = chunks

    def fetch(self, video_id: str, language: str = "") -> list[TranscriptChunk]:
        return list(self._chunks)

    def list_subtitles(self, video_id: str) -> list[SubtitleInfo]:
        return []
```

- [ ] **Step 4: Run test to verify it passes**

```bash
source .venv/bin/activate && python -m pytest tests/test_cached_transcript.py -v
```

Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/langmine/adapters/cached_transcript.py tests/test_cached_transcript.py
git commit -m "feat: add CachedTranscriptSource adapter for re-mining"
```

---

### Task 3: Re-mine API endpoint

**Files:**
- Modify: `src/langmine/web/routes/videos.py` (add `remine_video` route after `reclassify_sentences` at ~line 554)
- Modify: `tests/test_web_api.py` (add `TestRemineVideo` class)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_web_api.py` inside the `# === Fixtures ===` area or at end of file:

```python
import json


class TestRemineVideo:
    def test_remine_replaces_sentences(self, client):
        """POST /api/videos/<id>/remine should re-mine and replace sentences."""
        persistence = client.application.config["LANGMINE_PERSISTENCE"]

        # Prepare video with cached transcript
        from langmine.domain.models import Video

        video = Video(
            id=1,
            youtube_id="test_remine",
            title="Test Remine Video",
            language_code="zh",
            transcript_json=json.dumps(
                [
                    {"text": "你好", "start_ms": 0, "duration_ms": 1000},
                    {"text": "世界", "start_ms": 2000, "duration_ms": 1000},
                ]
            ),
        )
        persistence.save_video(video)

        resp = client.post("/api/videos/1/remine")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total_sentences"] == 2
        assert data["youtube_id"] == "test_remine"

        # New sentences were created
        sentences = persistence.get_sentences_by_video(1)
        assert len(sentences) == 2
        texts = {s.text for s in sentences}
        assert "你好" in texts
        assert "世界" in texts


    def test_remine_no_cached_transcript_returns_400(self, client):
        """Re-mine without cached transcript should return 400."""
        persistence = client.application.config["LANGMINE_PERSISTENCE"]

        from langmine.domain.models import Video

        video = Video(
            id=2,
            youtube_id="test_no_cache",
            title="No Cache Video",
            language_code="zh",
            transcript_json="",  # empty — no cached data
        )
        persistence.save_video(video)

        resp = client.post("/api/videos/2/remine")
        assert resp.status_code == 400
        data = resp.get_json()
        assert "No cached transcript" in data["error"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
source .venv/bin/activate && python -m pytest tests/test_web_api.py::TestRemineVideo -v
```

Expected: FAIL — 404 Not Found (route doesn't exist yet)

- [ ] **Step 3: Implement the re-mine endpoint**

Add to `src/langmine/web/routes/videos.py` after the `reclassify_sentences` route (after line 554):

```python
@videos_bp.route("/api/videos/<int:video_id>/remine", methods=["POST"])
def remine_video(video_id: int):
    """Re-mine a video from cached transcript and audio.

    Re-runs the full pipeline using cached data — no YouTube download.
    Streams progress via SSE (text/event-stream).
    """
    persistence = _get_persistence()
    processor = _get_processor()
    audio = _get_audio_processor()

    video = persistence.get_video(video_id)
    if not video or not video.transcript_json:
        return jsonify({"error": "No cached transcript found for this video"}), 400

    # Parse cached transcript
    import json as _json

    from langmine.adapters.cached_transcript import CachedTranscriptSource
    from langmine.domain.ports import TranscriptChunk

    raw = _json.loads(video.transcript_json)
    chunks = [
        TranscriptChunk(
            text=c["text"], start_ms=c["start_ms"], duration_ms=c["duration_ms"]
        )
        for c in raw
    ]
    transcript = CachedTranscriptSource(chunks)

    # ── Choose code path ────────────────────────────────────────────
    accept = request.headers.get("Accept", "")
    use_sse = "text/event-stream" in accept

    from langmine.pipeline import MineError

    if not use_sse:
        # Synchronous path — used by test client and non-browser clients.
        try:
            config = current_app.config["LANGMINE_CONFIG"]

            # Mark old sentences as deleted
            lang = _get_language_code()
            old_sentences = persistence.get_sentences_by_video(
                video.id, language_code=lang
            )
            for s in old_sentences:
                s.status = "deleted"
                persistence.update_sentence(s)

            result, updated_video = _mine_and_log(
                transcript=transcript,
                audio=audio,
                persistence=persistence,
                processor=processor,
                video_id=video.youtube_id,
                config=config,
            )
            return jsonify(_build_mine_result(updated_video, result, video.youtube_id))
        except MineError as e:
            return jsonify({"error": str(e), "stage": e.stage}), 400
        except Exception as e:
            return jsonify({"error": f"Re-mine failed: {e}"}), 500

    # SSE streaming path — live progress for the browser
    progress_queue: queue.Queue = queue.Queue()

    def _do_remine(app):
        """Run re-mine in a thread, pushing progress to the queue."""
        with app.app_context():
            try:
                config = current_app.config["LANGMINE_CONFIG"]

                def _on_progress(msg: str):
                    progress_queue.put(("progress", msg))

                # Mark old sentences as deleted
                p = _get_persistence()
                lang = _get_language_code()
                old_sentences = p.get_sentences_by_video(video.id, language_code=lang)
                for s in old_sentences:
                    s.status = "deleted"
                    p.update_sentence(s)

                result, updated_video = _mine_and_log(
                    transcript=transcript,
                    audio=audio,
                    persistence=p,
                    processor=processor,
                    video_id=video.youtube_id,
                    config=config,
                    progress_callback=_on_progress,
                )

                progress_queue.put(
                    ("done", _build_mine_result(updated_video, result, video.youtube_id))
                )
            except MineError as e:
                progress_queue.put(
                    ("error", {"error": str(e), "stage": e.stage})
                )
            except Exception as e:
                progress_queue.put(
                    ("error", {"error": f"Re-mine failed: {e}"})
                )

    app = current_app._get_current_object()
    thread = threading.Thread(target=_do_remine, args=(app,), daemon=True)
    thread.start()

    def generate():
        while True:
            try:
                msg_type, payload = progress_queue.get(timeout=600)
                if msg_type == "done":
                    yield f"data: {_json.dumps(payload)}\n\n"
                    break
                elif msg_type == "error":
                    yield f"data: {_json.dumps(payload)}\n\n"
                    break
                else:
                    yield f"data: {_json.dumps({'status': payload})}\n\n"
            except queue.Empty:
                break

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
source .venv/bin/activate && python -m pytest tests/test_web_api.py::TestRemineVideo -v
```

Expected: PASS (2 tests)

- [ ] **Step 5: Run full test suite**

```bash
source .venv/bin/activate && python -m pytest tests/test_web_api.py tests/test_pipeline.py tests/test_architecture.py tests/test_cached_transcript.py -v
```

All must pass.

- [ ] **Step 6: Commit**

```bash
git add src/langmine/web/routes/videos.py tests/test_web_api.py
git commit -m "feat: add POST /api/videos/<id>/remine endpoint"
```

---

### Task 4: Frontend API + store for re-mine

**Files:**
- Modify: `src/langmine/web/frontend/src/lib/api.js` (add `remineVideo` SSE generator)
- Modify: `src/langmine/web/frontend/src/lib/stores.svelte.js` (add `remineVideo` action)

- [ ] **Step 1: Add remineVideo to api.js**

In `src/langmine/web/frontend/src/lib/api.js`, inside the `api` object, after `reclassifySentences` (line 112), add:

```javascript
remineVideo: async function* (videoId) {
    const res = await fetch(BASE + `/videos/${videoId}/remine`, {
        method: 'POST',
        headers: { Accept: 'text/event-stream' }
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({ error: `${res.status}` }));
        throw new Error(err.error || `Re-mine failed (${res.status})`);
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
            if (line.startsWith('data: ')) {
                yield JSON.parse(line.slice(6));
            }
        }
    }
},
```

- [ ] **Step 2: Add remineVideo to stores.svelte.js**

In `src/langmine/web/frontend/src/lib/stores.svelte.js`, after the `mineVideo` function (after line 152), add:

```javascript
export async function remineVideo(videoId) {
    app.mining = true;
    app.mineStatus = '⏳ Re-mining...';
    try {
        let data;
        for await (const event of api.remineVideo(videoId)) {
            if (event.error) {
                throw new Error(event.error);
            } else if (event.status) {
                app.mineStatus = `⏳ ${event.status}`;
            } else {
                data = event;
            }
        }
        if (!data) {
            app.mineStatus = '❌ No result';
            return null;
        }
        app.mineStatus = `✅ ${data.total_sentences} sentences, ${data.i1_count} i+1`;
        await loadVideos();
        if (app.selectedVideoId === videoId) {
            await loadSentences(videoId, app.currentFilter);
        }
        return data;
    } catch (err) {
        console.error('[remine]', err);
        app.mineStatus = `❌ ${err.message}`;
        return null;
    } finally {
        app.mining = false;
    }
}
```

- [ ] **Step 3: Build frontend**

```bash
cd src/langmine/web/frontend && npm run build && cd -
```

Must succeed with no errors.

- [ ] **Step 4: Commit**

```bash
git add src/langmine/web/frontend/src/lib/api.js src/langmine/web/frontend/src/lib/stores.svelte.js
git commit -m "feat: add remineVideo to frontend API and store"
```

---

### Task 5: Re-mine button in sidebar

**Files:**
- Modify: `src/langmine/web/frontend/src/lib/Sidebar.svelte` (add button + styles)

- [ ] **Step 1: Import remineVideo in Sidebar.svelte**

Change line 2 from:
```svelte
import { app, selectVideo, mineVideo, exportAnki, deleteVideo } from './stores.svelte.js';
```
To:
```svelte
import { app, selectVideo, mineVideo, exportAnki, deleteVideo, remineVideo } from './stores.svelte.js';
```

- [ ] **Step 2: Add re-mine button to each video row**

In the `#each app.videos` block, add a re-mine button before the delete button (line 284):

```svelte
<button
    class="remine-video-btn"
    onclick={(e) => {
        e.stopPropagation();
        remineVideo(video.id);
    }}
    disabled={app.mining}
    title="Re-mine from cache">🔄</button
>
```

Place it between `</button>` (end of video-item) and the delete button:
```svelte
                    </button>
                    <button
                        class="remine-video-btn"
                        onclick={(e) => {
                            e.stopPropagation();
                            remineVideo(video.id);
                        }}
                        disabled={app.mining}
                        title="Re-mine from cache">🔄</button
                    >
                    <button
                        class="delete-video-btn"
```

- [ ] **Step 3: Add CSS styles for the re-mine button**

Add after the existing `.delete-video-btn:hover` rule (after line 535):

```css
.remine-video-btn {
    flex-shrink: 0;
    width: 36px;
    border: none;
    background: none;
    color: var(--text-secondary);
    cursor: pointer;
    font-size: 0.85rem;
    opacity: 0;
    transition:
        opacity 0.15s,
        color 0.15s;
}
.video-row:hover .remine-video-btn {
    opacity: 0.6;
}
.remine-video-btn:hover:not(:disabled) {
    opacity: 1 !important;
    color: var(--accent-green);
}
.remine-video-btn:disabled {
    opacity: 0.3;
    cursor: not-allowed;
}
```

- [ ] **Step 4: Build frontend**

```bash
cd src/langmine/web/frontend && npm run build && cd -
```

Must succeed.

- [ ] **Step 5: Run full test suite**

```bash
source .venv/bin/activate && python -m pytest tests/ -v --ignore=tests/test_audio.py
```

All must pass.

- [ ] **Step 6: Commit**

```bash
git add src/langmine/web/frontend/src/lib/Sidebar.svelte
git commit -m "feat: add re-mine button to video sidebar"
```
