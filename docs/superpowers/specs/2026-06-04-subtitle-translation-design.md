# Subtitle-Based Translation

**Date:** 2026-06-04
**Status:** design

## Problem

Translations currently come exclusively from Google Translate. Many YouTube videos have target-language subtitles (e.g., German subs for a Chinese video), which are human-authored and higher quality than MT. Users should be able to use those subtitle tracks as translation source instead of calling an MT API.

Additionally, the `translation_de` field is German-specific. It should be renamed to `translation` to be target-language-agnostic.

## Design

### Rename: `translation_de` → `translation`

| Layer | Files |
|-------|-------|
| Domain model | `domain/models.py`, `domain/classifier.py` |
| DB | `db.py` (schema: `translation_de` → `translation`), `sqlite_persistence.py`, migration |
| API | `web/routes/sentences.py`, `web/routes/videos.py`, `web/routes/_helpers.py` |
| Anki export | `adapters/anki_connect.py`, `config.py` (default templates), `languages/*/anki/*/back.html` |
| Frontend | `SentenceCard.svelte`, `TranscriptView.svelte`, `PreviewPanel.svelte` |
| E2E tests | `web/frontend/e2e/test_server.py` |
| Pytest | All test files referencing `translation_de` |

DB migration: `ALTER TABLE sentences RENAME COLUMN translation_de TO translation;`

Anki field rename: `{{translation_de}}` → `{{translation}}` in all templates and in `anki_connect.py` field mappings.

### New Module: `src/langmine/subtitle_aligner.py`

A single pure function:

```python
def align_target_subtitles(
    sentences: list[Sentence],
    target_chunks: list[TranscriptChunk],
) -> None:
    """For each sentence, set sentence.translation from overlapping
    target subtitle chunks. Sentences with no overlap are left as-is."""
```

Algorithm: time-overlap — for each sentence's `(start_ms, end_ms)` window, collect all target chunks where `chunk.start_ms < sentence.end_ms AND chunk_end > sentence.start_ms`, concatenated with space.

### Pipeline Change (`pipeline.py`)

`process_video()` accepts new parameter `target_subtitle_language: str = ""`. After merging source transcript into sentences and before classification/enrichment:

1. If `target_subtitle_language` is set: `target_chunks = transcript_source.fetch(video_id, language=target_subtitle_language)`
2. `align_target_subtitles(sentences, target_chunks)` — sets `sentence.translation` from subtitle overlap
3. Continue to classify + enrich as before

### Enrich Change (`classifier.py`)

In `enrich()`, only call `translate_sentence()` when `sentence.translation` is still empty. Subtitle-aligned sentences skip MT entirely. Sentences with no subtitle overlap fall through to MT.

### API Change

`POST /api/videos/mine` accepts new JSON field `target_subtitle_language` (optional string, empty = use MT). Passed through to `process_video()`.

### UI Change (`Sidebar.svelte`)

A second subtitle dropdown labeled "Translation" appears below the source subtitle dropdown. It shows available target-language subtitle tracks (filtered to match `config.target_language`), with an "🌐 Google Translate" default option. Auto-preselection matches the same strategy as the source dropdown: if a track's `language_code` starts with `config.target_language`, pre-select it.

### Frontend Data Flow

```
Sidebar.svelte: selectedTargetSubLang (state)
  → mineVideo(url, file, selectedSubLang)  // adds 4th param
  → stores.mineVideo(url, file, language)  // + targetLanguage
  → api.mineVideoStream(url, file, language, targetLanguage)
  → POST /api/videos/mine {language, target_subtitle_language}
```

### Test Plan

| Test | Type | What |
|------|------|------|
| `test_align_target_subtitles` | pytest unit | ~5 cases: full overlap, partial, no overlap, empty target, multiple matching chunks |
| `test_enrich_skips_mt_when_translation_present` | pytest | Pre-set `translation` on sentence, assert MT not called |
| `test_mine_accepts_target_subtitle_language` | pytest | Existing mine test pattern, verify param flows through |

No new E2E tests — the UI pattern mirrors the existing source subtitle dropdown which is already covered.
