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
