<script>
  import SentenceCard from './SentenceCard.svelte';
  import TranscriptView from './TranscriptView.svelte';
  import { app, curatedSentences, loadSentences, keepSentence, deleteSentence, markWordStatus, reclassifyAndLoad, addToast } from './stores.svelte.js';
  import { mergeWithPrevious } from './api.js';

  let { videoId } = $props();

  // M22: "Add Sentences" pagination state
  let hasMoreSentences = $state(false);
  let reclassifyLoading = $state(false);

  const FILTERS = [
    { key: 'all', label: 'All' },
    { key: 'i1', label: '🔥 i+1' },
    { key: 'kept', label: '✅ Kept' },
    { key: 'stashed', label: '📥 Stashed' },
    { key: 'deleted', label: '🗑 Deleted' },
  ];

  // Load sentences on first mount via $effect
  let loading = $state(true);
  $effect(() => {
    if (videoId) {
      loadSentences(videoId, 'all').finally(() => { loading = false; });
    }
  });

  // Client-side filtered sentences — pure $derived
  let filtered = $derived(
    curatedSentences().filter(s => app.currentFilter === 'all' || s.computedStatus === app.currentFilter)
  );

  // Empty state precedes cards in DOM order so Playwright always finds .empty-state
  let showEmpty = $derived(!loading && filtered.length === 0);

  async function setFilter(key) {
    app.currentFilter = key;
  }

  function onKeep(id) {
    keepSentence(id);
  }
  function onDelete(id) {
    deleteSentence(id);
  }

  // M24: sentence joining
  async function onMerge(id) {
    try {
      await mergeWithPrevious(id);
      await loadSentences(videoId, app.currentFilter);
      addToast('Merged', 'success');
    } catch (err) {
      addToast(`Merge failed: ${err.message}`, 'error');
    }
  }

  function toggleReadingMode() {
    app.readingMode = !app.readingMode;
  }

  // M22: trigger reclassification + load next page
  async function onAddSentences() {
    reclassifyLoading = true;
    const { hasMore } = await reclassifyAndLoad(videoId, 0, 50);
    hasMoreSentences = hasMore;
    reclassifyLoading = false;
  }

  async function onLoadMore() {
    reclassifyLoading = true;
    const { hasMore } = await reclassifyAndLoad(videoId, app.reclassifyOffset, 50);
    hasMoreSentences = hasMore;
    reclassifyLoading = false;
  }

  const EMPTY_MESSAGES = {
    all: 'No sentences for this video yet.',
    i1: 'No i+1 candidates. All words known or already curated! 🎉',
    kept: 'No sentences kept yet. Click 🟢 Keep to save sentences for export.',
    stashed: 'Stash is empty. Stashed sentences appear here when they drop to i+1.',
    deleted: 'No deleted sentences.',
  };

  let emptyMessage = $derived(EMPTY_MESSAGES[app.currentFilter] || 'Nothing to show.');
</script>

<nav class="tabs">
  {#each FILTERS as { key, label }}
    <button
      class="tab"
      class:active={app.currentFilter === key && !app.readingMode}
      onclick={() => { app.readingMode = false; setFilter(key); }}
    >
      {label}
    </button>
  {/each}
  <button
    class="tab"
    class:active={app.readingMode}
    onclick={toggleReadingMode}
  >
    📖 Read
  </button>
</nav>

<div class="cards-container">
  {#if app.readingMode}
    <TranscriptView {videoId} />
  {:else}
    {#if loading}
      <div class="empty-state">⏳ Loading...</div>
    {:else if showEmpty}
      <div class="empty-state">{emptyMessage}</div>
    {:else}
      {#each filtered as sentence, idx (sentence.id)}
        <SentenceCard {sentence} onkeep={onKeep} ondelete={onDelete} onmerge={onMerge} showMerge={idx > 0} wordStatuses={sentence.wordStatuses} />
      {/each}

      <!-- M22: Add Sentences button -->
      <div class="add-sentences-bar">
        {#if hasMoreSentences}
          <button class="add-sentences-btn" onclick={onLoadMore} disabled={reclassifyLoading}>
            {reclassifyLoading ? '⏳ Loading...' : '+ Add more sentences'}
          </button>
        {:else}
          <button class="add-sentences-btn" onclick={onAddSentences} disabled={reclassifyLoading}>
            {reclassifyLoading ? '⏳ Reclassifying...' : '🔄 Reclassify & sort'}
          </button>
        {/if}
      </div>
    {/if}
  {/if}
</div>

<style>
  .tabs {
    display: flex;
    gap: 4px;
    padding: 16px 24px 0;
    border-bottom: 1px solid var(--border);
    position: sticky;
    top: 0;
    background: var(--bg);
    z-index: 10;
  }
  .tab {
    padding: 8px 16px;
    background: none;
    border: none;
    border-bottom: 2px solid transparent;
    color: var(--text-secondary);
    font-size: 0.85rem;
    cursor: pointer;
    transition: color 0.15s, border-color 0.15s;
  }
  .tab:hover {
    color: var(--text);
  }
  .tab.active {
    color: var(--accent);
    border-bottom-color: var(--accent);
  }
  .cards-container {
    padding: 20px 24px;
  }
  .empty-state {
    text-align: center;
    color: var(--text-secondary);
    padding: 80px 0;
    font-size: 1rem;
    line-height: 1.6;
    max-width: 400px;
    margin: 0 auto;
  }
  .add-sentences-bar {
    text-align: center;
    padding: 24px 0;
  }
  .add-sentences-btn {
    padding: 10px 32px;
    background: var(--accent);
    color: var(--bg);
    border: none;
    border-radius: 8px;
    font-size: 0.95rem;
    cursor: pointer;
    transition: opacity 0.15s;
  }
  .add-sentences-btn:hover:not(:disabled) {
    opacity: 0.85;
  }
  .add-sentences-btn:disabled {
    opacity: 0.5;
    cursor: default;
  }
</style>
