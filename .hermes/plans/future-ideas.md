# Future Ideas

Ideas to revisit when the time is right. Not scheduled, not committed — just parked here so they aren't forgotten.

---

## Stats / Dashboard Page with Layer Cake

**Status:** parked
**Date:** 2026-06-01

### What

A dedicated stats view showing vocabulary acquisition metrics and mining analytics over time.

### Tooling

- **Layer Cake** ([layercake.graphics](https://layercake.graphics)) — headless graphics framework for Svelte. Handles responsive scales + SVG/Canvas layout; you write chart components as Svelte snippets. Philosophically aligned: you own the rendering, no black-box config.
- **shadcn-svelte** considered but rejected for now — not needed at current component count (9). Revisit if UI grows and you need accessible Dialog/Combobox/etc.

### What's needed before this makes sense

The current `/api/stats` returns 3 integers (`known`, `learning`, `total`). Layer Cake solves a problem you don't have yet. Before adding it:

1. **Time-series vocabulary data** — track known/learning counts over time: `[{date, known, learning}, ...]`
2. **Per-video breakdown** — known/unknown ratio per mined video
3. **Daily mining volume** — sentences mined per day
4. **Status distribution** — known / learning / ignored / unseen

### Possible charts

- Line chart: vocabulary growth over time (known, learning)
- Stacked bar: per-video known/unknown ratio
- Bar chart: daily mining volume
- Donut: status distribution

### Dependencies

- `layercake` (npm)
- Richer `/api/stats` endpoints (time-series queries)
- New `StatsPage.svelte` component
- Navigation tab in top bar

### Predecessors

- M25+ (any milestone that adds time-series tracking to vocab persistence)

---

## Auto-Translated Subtitles as Translation Source

**Status:** parked
**Date:** 2026-06-01

### What

YouTube auto-translates captions into dozens of languages. For example, a Chinese video has `de-zh German from Chinese` — a machine translation of the Chinese auto-captions into German. Instead of calling Google Translate, download the translated subtitle track and map translations to source sentences by timing.

### How

Add a second dropdown "Translation language" next to the source-language selector. Options: auto-translated tracks matching the learner's target language (e.g. "German from Chinese" for `source_language=zh-Hans`, target=German). When selected:

1. Download BOTH tracks: source (`zh-Hans`) + translated (`de-zh`)
2. Parse both into TranscriptChunks by timing
3. Map translated chunks to source sentence boundaries
4. Use translated text instead of Google Translate

Fall back to Google Translate when no matching auto-translated track exists.

### Example

Video: `NMoEqBiIVLA` — Chinese podcast, only auto captions
- Source: `zh-Hans-zh Chinese (Simplified) from Chinese` (auto-generated)
- Translations available: `de-zh German from Chinese`, `en-zh English from Chinese`, etc.

A German learner selects `de-zh` → every sentence gets a YouTube-translated German line with no API call.

### Dependencies

- `list_subtitles` already returns auto tracks (we filter them out today)
- `fetch_transcript` needs to support downloading a second track
- New UI: second `<select>` in Sidebar
- Modified `process_video` to accept an optional translation track
- Existing Google Translate path preserved as fallback
