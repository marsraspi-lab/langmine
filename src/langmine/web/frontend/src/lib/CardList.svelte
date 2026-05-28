<script>
  import SentenceCard from './SentenceCard.svelte';
  import { sentences, currentFilter, loadSentences, keepSentence, deleteSentence, markWordKnown } from './stores.js';

  let { videoId } = $props();

  const FILTERS = [
    { key: 'all', label: 'All' },
    { key: 'i1', label: '🔥 i+1' },
    { key: 'kept', label: '✅ Kept' },
    { key: 'deleted', label: '🗑 Deleted' },
  ];

  async function setFilter(key) {
    currentFilter.set(key);
    await loadSentences(videoId, key);
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
  {#if $sentences.length === 0}
    <div class="empty-state">No sentences to show.</div>
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
  }
</style>
