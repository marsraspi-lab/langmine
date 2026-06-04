<script>
  import { searchImages, setClozeImage } from './api.js';
  import { addToast } from './stores.svelte.js';

  let { word, sentenceId, onClose } = $props();

  let images = $state([]);
  let loading = $state(false);
  let selectedUrl = $state(null);
  let saving = $state(false);

  async function doSearch() {
    loading = true;
    images = [];
    selectedUrl = null;
    try {
      const data = await searchImages(word, 5);
      images = data.images || [];
      if (images.length === 0) {
        addToast(`No images found for "${word}"`, 'info', 3000);
      }
    } catch (err) {
      addToast(`Search failed: ${err.message}`, 'error');
    } finally {
      loading = false;
    }
  }

  async function selectImage(url) {
    selectedUrl = url;
    saving = true;
    try {
      await setClozeImage(sentenceId, url);
      addToast('Image saved for cloze hint ✓', 'success', 2000);
      onClose?.();
    } catch (err) {
      addToast(`Failed: ${err.message}`, 'error');
    } finally {
      saving = false;
    }
  }
</script>

<div class="image-picker-overlay"
     onclick={onClose}
     onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ' || e.key === 'Escape') onClose(); }}
     role="button"
     tabindex="0"
     aria-label="Close image picker"
></div>
<div class="image-picker-modal">
  <div class="image-picker-header">
    <span>🖼️ Images for "{word}"</span>
    <button class="image-picker-close" onclick={onClose}>✕</button>
  </div>

  {#if loading}
    <div class="image-picker-loading">🔍 Searching...</div>
  {:else if images.length === 0}
    <button class="image-picker-search-btn" onclick={doSearch}>
      🔍 Search images
    </button>
  {:else}
    <div class="image-grid">
      {#each images as url}
        <button
          class="image-grid-item"
          class:selected={selectedUrl === url}
          onclick={() => selectImage(url)}
          disabled={saving}
        >
          <img src={url} alt={word} loading="lazy" />
        </button>
      {/each}
    </div>
  {/if}

  {#if saving}
    <div class="image-picker-saving">Saving...</div>
  {/if}
</div>

<style>
  .image-picker-overlay {
    position: fixed; inset: 0; z-index: 200;
    background: rgba(0, 0, 0, 0.5);
  }
  .image-picker-modal {
    position: fixed;
    left: 50%; top: 50%;
    transform: translate(-50%, -50%);
    z-index: 210;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px;
    min-width: 320px;
    max-width: 480px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.5);
  }
  .image-picker-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
    font-size: 0.9rem;
  }
  .image-picker-close {
    background: none; border: none;
    color: var(--text-secondary);
    cursor: pointer; font-size: 1rem;
  }
  .image-picker-loading, .image-picker-saving {
    text-align: center;
    color: var(--text-secondary);
    padding: 24px 0;
  }
  .image-picker-search-btn {
    width: 100%;
    padding: 10px;
    background: var(--accent);
    color: white;
    border: none;
    border-radius: var(--radius);
    cursor: pointer;
    font-size: 0.9rem;
  }
  .image-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
  }
  .image-grid-item {
    background: none;
    border: 2px solid transparent;
    border-radius: 4px;
    padding: 0;
    cursor: pointer;
    overflow: hidden;
    aspect-ratio: 1;
  }
  .image-grid-item:hover {
    border-color: var(--accent);
  }
  .image-grid-item.selected {
    border-color: var(--accent-green);
  }
  .image-grid-item img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }
  .image-grid-item:disabled {
    opacity: 0.5;
    cursor: wait;
  }
</style>
