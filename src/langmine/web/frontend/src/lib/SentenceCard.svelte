<script>
  import { fly } from 'svelte/transition';

  /** @type {{ sentence: Object, onkeep: Function, ondelete: Function, oniknowthis: Function }} */
  let { sentence, onkeep = () => {}, ondelete = () => {}, oniknowthis = () => {} } = $props();

  const STATUS_LABELS = {
    i1: 'i+1',
    i0: 'known',
    kept: 'kept',
    deleted: 'deleted',
    stashed: 'stashed',
  };

  function highlightUnknown(text, word) {
    if (!word) return text;
    const escaped = word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const parts = text.split(new RegExp(`(${escaped})`, 'g'));
    return parts.map(part =>
      part === word
        ? `<span class="unknown-word-highlight">${part}</span>`
        : part
    ).join('');
  }
</script>

<div class="sentence-card" transition:fly={{ y: 20, duration: 200 }}>
  <div class="card-header">
    <span class="chinese-text">
      {@html highlightUnknown(sentence.text, sentence.unknown_word)}
    </span>
    <span class="status-badge {sentence.status}">{STATUS_LABELS[sentence.status] || sentence.status}</span>
  </div>

  {#if sentence.pinyin}
    <div class="pinyin-text">{sentence.pinyin}</div>
  {/if}

  {#if sentence.translation_de}
    <div class="translation-text">{sentence.translation_de}</div>
  {/if}

  {#if sentence.text_segmented}
    <div class="segmented-text">{sentence.text_segmented}</div>
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
    <button class="btn-delete" onclick={() => ondelete(sentence.id)}>
      🔴 Delete
    </button>
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
  }
  .translation-text {
    font-size: 0.95rem;
    color: var(--text-secondary);
    margin-bottom: 8px;
  }
  .segmented-text {
    font-size: 0.85rem;
    color: var(--text-secondary);
    margin-bottom: 12px;
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
