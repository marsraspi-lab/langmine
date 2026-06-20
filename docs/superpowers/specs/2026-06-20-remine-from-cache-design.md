# Re-mine from Cache

**Date:** 2026-06-20
**Status:** approved

## Problem

Every time the user mines a video, LangMine re-downloads the transcript and audio from YouTube. This is slow, hits rate limits, and makes iterative testing painful. The `video.transcript_json` column already exists in the schema but is never populated.

## Design

Cache the raw transcript chunks during initial mining, then add a "re-mine" feature that re-runs the full pipeline from cached data.

### Flow

**Initial mine (updated):**
```
YouTube → fetch transcript → cache as JSON → merge → classify → enrich → screenshots + audio clips → persist sentences
                                  ↑
                          video.transcript_json
```

**Re-mine (new):**
```
video.transcript_json → CachedTranscriptSource → merge → classify → enrich → screenshots + audio clips → replace sentences
video.audio_path ──────────────────────────────────────────────────────────────────────────────────────┘
```

### Components

#### 1. Cache transcript (`pipeline.py`)
- After `_fetch_and_merge_transcript()`, serialize raw chunks to `video.transcript_json`
- JSON array of `{text, start_ms, duration_ms}` — raw chunks before merge, so `gap_ms` can change on re-mine

#### 2. `CachedTranscriptSource` (new file: `adapters/cached_transcript.py`)
- Implements `TranscriptSource` port
- Constructor takes `list[TranscriptChunk]`
- `fetch()` returns the list verbatim
- `list_subtitles()` returns `[]` (not needed for re-mine)

#### 3. Re-mine endpoint (`routes/videos.py`)
- `POST /api/videos/<int:video_id>/remine`
- SSE streaming, same pattern as `POST /api/videos/mine`
- Steps:
  1. Load video from persistence
  2. Parse `transcript_json` → `list[TranscriptChunk]`
  3. Create `CachedTranscriptSource`
  4. Check `video.audio_path` exists on disk (best-effort; skip audio clips if missing)
  5. Delete old sentences for this video
  6. Run `process_video()` with cached transcript and audio
  7. Return result via SSE

#### 4. Frontend (`Sidebar.svelte`, `stores.svelte.js`, `api.js`)
- Re-mine button (🔄) next to delete button on each video row
- `api.remineVideo(videoId)` — async generator, SSE stream
- `stores.remineVideo(videoId)` — manages mining state, calls `api.remineVideo`, refreshes on completion

### What gets regenerated

| Data | Source | Notes |
|------|--------|-------|
| Transcript chunks | `video.transcript_json` | Raw, re-merged with current `gap_ms` |
| Audio | `video.audio_path` | Already on disk; re-clipped for each sentence |
| Classifications | From scratch | Uses current known-word vocab |
| Enrichment (translations) | Fresh MT calls | New translations |
| Screenshots | Re-captured | From cached video frames |
| Sentences | Replaced | Old sentences deleted, new ones saved |

### Architecture compliance

- `CachedTranscriptSource` lives in `adapters/` — implements `TranscriptSource` port
- `pipeline.py` does NOT import from `adapters/` — it just writes `transcript_json` on the `Video` model
- Re-mine route in `routes/videos.py` imports from `adapters/cached_transcript` and `pipeline`
- `app.py` does NOT need changes — `CachedTranscriptSource` is created inline in the route

### Testing

- **Unit:** `CachedTranscriptSource` returns chunks, `fetch()` with language param is a no-op
- **Pipeline:** `test_process_video_caches_transcript_json` — verify `video.transcript_json` is set
- **API:** `test_remine_endpoint` — SSE stream, sentences are replaced, audio re-clipped
- **E2E:** Re-mine button visible, click triggers re-mine, new sentences appear
