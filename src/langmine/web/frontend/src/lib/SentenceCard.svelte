<script>
  import { fly } from 'svelte/transition';
  import { updateSentenceField } from './stores.js';

  /** @type {{ sentence: Object, onkeep: Function, ondelete: Function, oniknowthis: Function }} */
  let { sentence, onkeep = () => {}, ondelete = () => {}, oniknowthis = () => {} } = $props();

  const STATUS_LABELS = {
    i1: 'i+1',
    i0: 'known',
    kept: 'kept',
    deleted: 'deleted',
    stashed: 'stashed',
  };

  // Editable fields
  let editingField = $state(null);
  let editValue = $state('');
  let saving = $state(false);

  function startEdit(field) {
    editingField = field;
    editValue = sentence[field] || '';
  }

  function cancelEdit() {
    editingField = null;
    editValue = '';
  }

  async function saveEdit(field) {
    if (editValue === sentence[field]) {
      cancelEdit();
      return;
    }
    saving = true;
    try {
      await updateSentenceField(sentence.id, { [field]: editValue });
      cancelEdit();
    } catch {
      // Error toast shown by store
    } finally {
      saving = false;
    }
  }

  function handleEditKeydown(e, field) {
    if (e.key === 'Enter') saveEdit(field);
    if (e.key === 'Escape') cancelEdit();
  }

  function highlightUnknown(text, word) {
    if (!word) return text;
    const escaped = word.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&');
    const parts = text.split(new RegExp(`(${escaped})`, 'g'));
    return parts.map(part =>
      part === word
        ? `<span class="unknown-word-highlight">${part}</span>`
        : part
    ).join('');
  }

  let SHOW_DELETE_CONFIRM = $state(false);
  function confirmDelete() { SHOW_DELETE_CONFIRM = true; }
  function cancelDeleteConfirm() { SHOW_DELETE_CONFIRM = false; }
  function doDelete() {
    SHOW_DELETE_CONFIRM = false;
    ondelete(sentence.id);
  }
</script>

<div class="sentence-card" transition:fly={{ y: 20, duration: 200 }}>
  <div class="card-header">
    <span class="chinese-text">
      {@html highlightUnknown(sentence.text, sentence.unknown_word)}
    </span>
    <span class="status-badge {sentence.status}">{STATUS_LABELS[sentence.status] || sentence.status}</span>
  </div>

  {#if editingField === 'pinyin' || sentence.pinyin}
    <div class="editable-field" class:saving>
      {#if editingField === 'pinyin'}
        <input
          type="text"
          class="edit-input pinyin-input"
          bind:value={editValue}
          onkeydown={(e) => handleEditKeydown(e, 'pinyin')}
          onblur={() => saveEdit('pinyin')}
          autofocus
        />
      {:else}
        <span class="pinyin-text" onclick={() => startEdit('pinyin')} title="Click to edit">
          {sentence.pinyin}
        </span>
      {/if}
    </div>
  {/if}

  {#if editingField === 'translation_de' || sentence.translation_de}
    <div class="editable-field" class:saving>
      {#if editingField === 'translation_de'}
        <input
          type="text"
          class="edit-input translation-input"
          bind:value={editValue}
          onkeydown={(e) => handleEditKeydown(e, 'translation_de')}
          onblur={() => saveEdit('translation_de')}
          autofocus
        />
      {:else}
        <span class="translation-text" onclick={() => startEdit('translation_de')} title="Click to edit">
          {sentence.translation_de}
        </span>
      {/if}
    </div>
  {/if}

  {#if editingField === 'text_segmented' || sentence.text_segmented}
    <div class="editable-field" class:saving>
      {#if editingField === 'text_segmented'}
        <input
          type="text"
          class="edit-input seg-input"
          bind:value={editValue}
          onkeydown={(e) => handleEditKeydown(e, 'text_segmented')}
          onblur={() => saveEdit('text_segmented')}
          autofocus
        />
      {:else}
        <span class="segmented-text" onclick={() => startEdit('text_segmented')} title="Click to edit (re-classifies)">
          {sentence.text_segmented}
        </span>
      {/if}
    </div>
  {/if}

  {#if sentence.has_audio}
    <div class="audio-player">
      <audio controls src="/api/sentences/{sentence.id}/audio"></audio>
    </div>
  {/if}

  {#if sentence.has_screenshot}
    <div class="screenshot-thumb">
      <img src="/api/sentences/{sentence.id}/screenshot" alt="Screenshot" />
    </div>
  {/if}

  {#if sentence.unknown_word}
    <div class="word-info">
      {sentence.frequency_badge || ''} <strong>{sentence.unknown_word}</strong>
      {#if sentence.unknown_word_rank}
        <span class="rank">(rank #{sentence.unknown_word_rank})</span>
      {/if}
    </div>
  {/if}

  <div class="card-actions">
    <button class="btn-keep" onclick={() => onkeep(sentence.id)}>
      🟢 Keep
    </button>
    {#if SHOW_DELETE_CONFIRM}
      <button class="btn-delete" onclick={doDelete}>
        ⚠️ Confirm delete
      </button>
      <button class="btn-cancel" onclick={cancelDeleteConfirm}>
        Cancel
      </button>
    {:else}
      <button class="btn-delete" onclick={confirmDelete}>
        🔴 Delete
      </button>
    {/if}
    {#if sentence.unknown_word}
      <button class="btn-iknow" onclick={() => oniknowthis(sentence.id)}>
        📖 I Know This
      </button>
    {/if}
  </div>
</div>

<style>
  .sentence-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 20px;
    margin-bottom: 12px;
  }
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 12px;
    margin-bottom: 8px;
  }
  .chinese-text {
    font-size: 1.3rem;
    line-height: 1.6;
  }
  .pinyin-text {
    font-size: 0.9rem;
    color: var(--accent-green);
    margin-bottom: 4px;
    font-style: italic;
    cursor: pointer;
  }
  .pinyin-text:hover {
    text-decoration: underline;
    text-decoration-style: dotted;
  }
  .translation-text {
    font-size: 0.95rem;
    color: var(--text-secondary);
    margin-bottom: 8px;
    cursor: pointer;
  }
  .translation-text:hover {
    text-decoration: underline;
    text-decoration-style: dotted;
  }
  .segmented-text {
    font-size: 0.85rem;
    color: var(--text-secondary);
    margin-bottom: 12px;
    cursor: pointer;
  }
  .segmented-text:hover {
    text-decoration: underline;
    text-decoration-style: dotted;
  }
  .editable-field {
    margin-bottom: 4px;
  }
  .edit-input {
    width: 100%;
    padding: 4px 8px;
    background: var(--bg);
    border: 1px solid var(--accent);
    border-radius: 4px;
    color: var(--text);
    font-size: inherit;
    font-family: inherit;
  }
  .pinyin-input {
    font-size: 0.9rem;
    font-style: italic;
    color: var(--accent-green);
  }
  .translation-input {
    font-size: 0.95rem;
  }
  .seg-input {
    font-size: 0.85rem;
  }
  .saving {
    opacity: 0.6;
  }
  .audio-player {
    margin: 12px 0;
  }
  .audio-player audio {
    width: 100%;
    height: 32px;
  }
  .screenshot-thumb {
    margin: 12px 0;
  }
  .screenshot-thumb img {
    max-width: 100%;
    max-height: 200px;
    border-radius: 4px;
    border: 1px solid var(--border);
  }
  .word-info {
    font-size: 0.8rem;
    color: var(--text-secondary);
    margin-bottom: 12px;
  }
  .rank {
    opacity: 0.7;
  }
  .card-actions {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }
  .card-actions button {
    padding: 6px 16px;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: transparent;
    color: var(--text);
    font-size: 0.85rem;
    cursor: pointer;
    transition: background 0.15s;
  }
  .card-actions button:hover {
    background: rgba(255, 255, 255, 0.1);
  }
  .btn-keep {
    border-color: var(--accent-green) !important;
    color: var(--accent-green) !important;
  }
  .btn-keep:hover {
    background: rgba(78, 204, 163, 0.15) !important;
  }
  .btn-delete {
    border-color: var(--accent) !important;
    color: var(--accent) !important;
  }
  .btn-delete:hover {
    background: rgba(233, 69, 96, 0.15) !important;
  }
  .btn-cancel {
    border-color: var(--text-secondary) !important;
    color: var(--text-secondary) !important;
  }
  .btn-iknow {
    border-color: var(--text-secondary) !important;
  }

  :global(.unknown-word-highlight) {
    color: var(--accent);
    font-weight: 700;
    text-decoration: underline;
    text-decoration-style: dotted;
    text-underline-offset: 4px;
  }
  :global(.status-badge) {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 600;
    white-space: nowrap;
  }
  :global(.status-badge.i1) {
    background: rgba(233, 69, 96, 0.2);
    color: var(--accent);
  }
  :global(.status-badge.kept) {
    background: rgba(78, 204, 163, 0.2);
    color: var(--accent-green);
  }
  :global(.status-badge.i0) {
    background: rgba(160, 160, 176, 0.2);
    color: var(--text-secondary);
  }
  :global(.status-badge.deleted) {
    background: rgba(160, 160, 176, 0.1);
    color: var(--text-secondary);
    text-decoration: line-through;
  }
  :global(.status-badge.stashed) {
    background: rgba(255, 193, 7, 0.2);
    color: #ffc107;
  }
</style>
