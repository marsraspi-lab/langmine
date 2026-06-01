<script>
  import { fly } from 'svelte/transition';
  import { updateSentenceField, markWordStatus } from './stores.js';
  import { updateVocabWord } from './api.js';
  import { currentView, vocabSearchQuery } from './stores.js';

  /** @type {{ sentence: Object, onkeep: Function, ondelete: Function, oniknowthis: Function }} */
  let { sentence, onkeep = () => {}, ondelete = () => {}, wordStatuses = {} } = $props();

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

  function startSegmentedEdit() {
    // Convert "word / word" format to space-separated for editing
    editingField = 'text_segmented';
    editValue = (sentence.text_segmented || '').replace(/ \/ /g, ' ');
  }

  function cancelEdit() {
    editingField = null;
    editValue = '';
  }

  async function saveEdit(field) {
    let value = editValue;
    // Convert space-separated words back to " / " format for text_segmented
    if (field === 'text_segmented') {
      value = value.trim().split(/\\s+/).join(' / ');
    }
    if (value === sentence[field]) {
      cancelEdit();
      return;
    }
    saving = true;
    try {
      await updateSentenceField(sentence.id, { [field]: value });
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

  // ---- Word highlighting & status toggle ----

  let activeWordIdx = $state(null);
  let togglingWord = $state(null);

  // Build derived words array from client-side wordStatuses (M19)
  let displayWords = $derived(
    wordStatuses && Object.keys(wordStatuses).length > 0
      ? Object.entries(wordStatuses).map(([token, status]) => ({
          token,
          status,
          frequency_rank: null,
          hsk_level: null,
        }))
      : (sentence.words || []).map((w) => ({
          token: w.token,
          status: w.status || 'unknown',
          frequency_rank: w.frequency_rank,
          hsk_level: w.hsk_level,
        }))
  );

  function freqBadge(rank) {
    if (rank === null || rank === undefined) return null;
    if (rank <= 500) return '🔥';
    if (rank <= 3000) return '⭐';
    return '💎';
  }

  function freqRank(rank) {
    if (rank === null || rank === undefined) return null;
    return `#${rank}`;
  }

  function togglePopover(idx) {
    if (activeWordIdx === idx) {
      activeWordIdx = null;
    } else {
      activeWordIdx = idx;
    }
  }

  function closePopover() {
    activeWordIdx = null;
  }

  function showInDictionary(token) {
    vocabSearchQuery.set(token);
    currentView.set('vocab');
  }

  async function toggleWordStatus(wordObj, idx) {
    const nextStatus =
      wordObj.status === 'unknown' ? 'learning' :
      wordObj.status === 'learning' ? 'known' :
      'unknown';
    togglingWord = idx;
    try {
      await markWordStatus(wordObj.token, nextStatus);
    } finally {
      togglingWord = null;
    }
  }

  function handleWordStatusClick(wordObj, idx, newStatus) {
    togglingWord = idx;
    markWordStatus(wordObj.token, newStatus).finally(() => {
      togglingWord = null;
    });
    closePopover();
  }

  function handleWordClick(wordObj, idx) {
    togglePopover(idx);
  }

  // Handle click outside to close popover
  function handleDocClick(e) {
    // Svelte on:click outside isn't available in Svelte 5, use global handler
    // Handled via svelte:window below in the component
  }

  function onWindowClick(e) {
    if (activeWordIdx !== null) {
      // Check if click is outside any word popover
      const popover = document.querySelector('.word-popover');
      if (popover && !popover.contains(e.target)) {
        // Check if the click target is a word itself (let the word handler toggle)
        if (!e.target.closest('.word-token')) {
          closePopover();
        }
      }
    }
  }

  let SHOW_DELETE_CONFIRM = $state(false);
  function confirmDelete() { SHOW_DELETE_CONFIRM = true; }
  function cancelDeleteConfirm() { SHOW_DELETE_CONFIRM = false; }
  function doDelete() {
    SHOW_DELETE_CONFIRM = false;
    ondelete(sentence.id);
  }
</script>

<svelte:window onclick={onWindowClick} />

<div class="sentence-card" transition:fly={{ y: 20, duration: 200 }}>
  <div class="card-header">
    <span class="chinese-text">
      {#if displayWords.length > 0}
        {#each displayWords as word, idx}
          <span
            class="word-token word-{word.status}"
            class:word-toggling={togglingWord === idx}
            onclick={() => handleWordClick(word, idx)}
            role="button"
            tabindex="0"
            onkeydown={(e) => e.key === 'Enter' && handleWordClick(word, idx)}
          >
            {word.token}
          </span>
        {/each}
      {:else}
        {sentence.text}
      {/if}
    </span>
    <span class="status-badge {sentence.status}">{STATUS_LABELS[sentence.status] || sentence.status}</span>
  </div>

  {#if editingField === 'reading' || sentence.reading}
    <div class="editable-field" class:saving>
      {#if editingField === 'reading'}
        <input
          type="text"
          class="edit-input reading-input"
          bind:value={editValue}
          onkeydown={(e) => handleEditKeydown(e, 'reading')}
          onblur={() => saveEdit('reading')}
          autofocus
        />
      {:else}
        <span class="reading-text" onclick={() => startEdit('reading')} title="Click to edit">
          {sentence.reading}
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
          class="edit-input segmented-input"
          bind:value={editValue}
          onkeydown={(e) => handleEditKeydown(e, 'text_segmented')}
          onblur={() => saveEdit('text_segmented')}
          autofocus
        />
      {:else}
        <span class="segmented-text" onclick={() => startSegmentedEdit()} title="Click to edit segmentation">
          {sentence.text_segmented}
        </span>
      {/if}
    </div>
  {/if}

  <!-- Word-level annotation badges row -->
  {#if displayWords.length > 0}
    <div class="word-annotations">
      {#each displayWords as word, idx}
        {#if word.status === 'unknown' || word.status === 'learning'}
          <span class="word-annotation word-annotation-{idx}">
            {#if word.hsk_level}
              <span class="hsk-badge hsk-{word.hsk_level}">HSK{word.hsk_level}</span>
            {/if}
            {#if word.frequency_rank}
              <span class="freq-badge" title="Rank {word.frequency_rank}">{freqBadge(word.frequency_rank)} {freqRank(word.frequency_rank)}</span>
            {/if}
          </span>
        {/if}
      {/each}
    </div>
  {/if}

  <!-- Word status popover -->
  {#if activeWordIdx !== null && displayWords[activeWordIdx]}
    {@const word = displayWords[activeWordIdx]}
    <div class="word-popover">
      <div class="popover-word">{word.token}</div>
      <div class="popover-status">
        Status: <span class="popover-status-badge word-{word.status}">{word.status}</span>
      </div>
      <div class="popover-actions">
        <button
          class="popover-btn btn-mark-known"
          onclick={() => handleWordStatusClick(word, activeWordIdx, 'known')}
          disabled={togglingWord === activeWordIdx || word.status === 'known'}
        >
          ✅ Mark known
        </button>
        <button
          class="popover-btn btn-mark-learning"
          onclick={() => handleWordStatusClick(word, activeWordIdx, 'learning')}
          disabled={togglingWord === activeWordIdx || word.status === 'learning'}
        >
          📚 Mark learning
        </button>
        <button
          class="popover-btn btn-mark-ignored"
          onclick={() => handleWordStatusClick(word, activeWordIdx, 'ignored')}
          disabled={togglingWord === activeWordIdx || word.status === 'ignored'}
        >
          🚫 Ignore
        </button>
        {#if word.status !== 'proper-name'}
          <button
            class="popover-btn"
            onclick={() => handleWordStatusClick(word, activeWordIdx, 'proper-name')}
            disabled={togglingWord === activeWordIdx}
          >👤 Mark as proper name</button>
        {/if}
        <button
          class="popover-btn"
          onclick={() => showInDictionary(word.token)}
        >📋 Show in dictionary</button>
      </div>
      <button class="popover-close" onclick={closePopover}>✕</button>
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
  </div>
</div>

<style>
  .sentence-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 20px;
    margin-bottom: 12px;
    position: relative;
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
    line-height: 1.8;
    display: flex;
    flex-wrap: wrap;
    gap: 2px 6px;
  }

  /* --- Word tokens --- */
  .word-token {
    cursor: pointer;
    padding: 1px 4px;
    border-radius: 3px;
    transition: background 0.15s, opacity 0.15s;
    user-select: none;
    position: relative;
  }
  .word-token:hover {
    filter: brightness(1.2);
  }
  .word-toggling {
    opacity: 0.5;
  }

  .word-known {
    color: var(--accent-green, #4ecca3);
  }
  .word-learning {
    color: #ffa726;
    border-bottom: 2px dotted #ffa726;
  }
  .word-unknown {
    color: var(--accent, #e94560);
    border-bottom: 2px dotted var(--accent, #e94560);
  }
  .word-ignored {
    color: var(--text-secondary, #999);
    text-decoration: line-through;
  }

  /* --- Word annotations row --- */
  .word-annotations {
    display: flex;
    flex-wrap: wrap;
    gap: 4px 8px;
    margin-bottom: 8px;
    font-size: 0.75rem;
  }
  .word-annotation {
    display: inline-flex;
    align-items: center;
    gap: 3px;
  }
  .hsk-badge {
    display: inline-block;
    padding: 1px 5px;
    border-radius: 3px;
    font-size: 0.7rem;
    font-weight: 700;
    background: rgba(100, 149, 237, 0.25);
    color: #6495ed;
  }
  .freq-badge {
    display: inline-block;
    padding: 1px 5px;
    border-radius: 3px;
    font-size: 0.7rem;
    background: rgba(255, 255, 255, 0.08);
    color: var(--text-secondary);
  }

  /* --- Word popover --- */
  .word-popover {
    position: absolute;
    top: 80px;
    left: 20px;
    z-index: 100;
    background: var(--bg-card, #1e1e2e);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 14px 18px;
    min-width: 180px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.4);
  }
  .popover-word {
    font-size: 1.1rem;
    font-weight: 600;
    margin-bottom: 8px;
    color: var(--text);
  }
  .popover-status {
    font-size: 0.8rem;
    color: var(--text-secondary);
    margin-bottom: 10px;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .popover-status-badge {
    display: inline-block;
    padding: 1px 8px;
    border-radius: 3px;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: capitalize;
  }
  .popover-status-badge.word-known {
    background: rgba(78, 204, 163, 0.2);
    border-bottom: none;
  }
  .popover-status-badge.word-learning {
    background: rgba(255, 167, 38, 0.2);
    border-bottom: none;
  }
  .popover-status-badge.word-ignored {
    background: rgba(150, 150, 150, 0.2);
    border-bottom: none;
  }
  .popover-status-badge.word-unknown {
    background: rgba(233, 69, 96, 0.2);
    border-bottom: none;
  }
  .popover-actions {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .popover-btn {
    padding: 5px 12px;
    border: 1px solid var(--border);
    border-radius: 4px;
    background: transparent;
    color: var(--text);
    font-size: 0.8rem;
    cursor: pointer;
    text-align: left;
    transition: background 0.15s;
  }
  .popover-btn:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.08);
  }
  .popover-btn:disabled {
    opacity: 0.4;
    cursor: default;
  }
  .btn-mark-known {
    border-color: var(--accent-green, #4ecca3);
  }
  .btn-mark-learning {
    border-color: #ffa726;
  }
  .popover-close {
    position: absolute;
    top: 6px;
    right: 10px;
    background: none;
    border: none;
    color: var(--text-secondary);
    font-size: 0.9rem;
    cursor: pointer;
    padding: 2px 4px;
  }
  .popover-close:hover {
    color: var(--text);
  }

  .reading-text {
    font-size: 0.9rem;
    color: var(--accent-green);
    margin-bottom: 4px;
    font-style: italic;
    cursor: pointer;
  }
  .reading-text:hover {
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
  .reading-input {
    font-size: 0.9rem;
    font-style: italic;
    color: var(--accent-green);
  }
  .translation-input {
    font-size: 0.95rem;
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
