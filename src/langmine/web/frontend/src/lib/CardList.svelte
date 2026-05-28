<script>
  import SentenceCard from './SentenceCard.svelte';
  import { sentences, currentFilter, loadSentences, keepSentence, deleteSentence, markWordKnown } from './stores.js';

  let { videoId } = $props();

  const FILTERS = [
    { key: 'all', label: 'All' },
    { key: 'i1', label: '🔥 i+1' },
    { key: 'kept', label: '✅ Kept' },
    { key: 'stashed', label: '📥 Stashed' },
    { key: 'deleted', label: '🗑 Deleted' },
  ];

  let loading = $state(false);

  async function setFilter(key) {
    currentFilter.set(key);
    loading = true;
    try {
      await loadSentences(videoId, key);
    } finally {
      loading = false;
    }
  }

  function onKeep(id) {
    keepSentence(id);
  }
  function onDelete(id) {
    deleteSentence(id);
  }
  function onIknowthis(id) {
    markWordKnown(id);
  }

  const EMPTY_MESSAGES = {
    all: 'No sentences for this video yet.',
    i1: 'No i+1 candidates. All words known or already curated! 🎉',
    kept: 'No sentences kept yet. Click 🟢 Keep to save sentences for export.',
    stashed: 'Stash is empty. Stashed sentences appear here when they drop to i+1.',
    deleted: 'No deleted sentences.',
  };

  let emptyMessage = $derived(EMPTY_MESSAGES[$currentFilter] || 'Nothing to show.');
</script>

<nav class="tabs">
  {#each FILTERS as { key, label }}
    <button
      class="tab"
      class:active={$currentFilter === key}
      onclick={() => setFilter(key)}
    >
      {label}
    </button>
  {/each}
</nav>

<div class="cards-container">
  {#if loading}
    <div class="empty-state">⏳ Loading...</div>
  {:else if $sentences.length === 0}
    <div class="empty-state">{emptyMessage}</div>
  {:else}
    {#each $sentences as sentence (sentence.id)}
      <SentenceCard {sentence} onkeep={onKeep} ondelete={onDelete} oniknowthis={onIknowthis} />
    {/each}
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
</style>
