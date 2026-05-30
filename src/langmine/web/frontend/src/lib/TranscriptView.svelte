<script>
  import { onMount } from 'svelte';
  import { updateVocabWord } from './api.js';
  import { addToast, currentView, vocabSearchQuery } from './stores.js';
  import ImagePicker from './ImagePicker.svelte';

  let { videoId } = $props();

  let sentences = $state([]);
  let loading = $state(true);
  let showTranslation = $state(false);
  let showLegend = $state(false);
  let showRuby = $state(false);
  let activeWord = $state(null);
  let activeSentenceIdx = $state(0);
  let showImagePicker = $state(false);

  // Pleco tone colors: 1=red, 2=green, 3=blue, 4=purple, 5=gray
  const TONE_COLORS = ['', '#E53935', '#43A047', '#1E88E5', '#8E24AA', '#9E9E9E'];

  onMount(loadTranscript);

  async function loadTranscript() {
    loading = true;
    try {
      const res = await fetch(`/api/videos/${videoId}/transcript`);
      const data = await res.json();
      sentences = data.sentences || [];
    } catch (err) {
      addToast('Failed to load transcript', 'error');
    } finally {
      loading = false;
    }
  }

  function playAudio(sentence) {
    if (!sentence.has_audio) return;
    new Audio(`/api/sentences/${sentence.id}/audio`).play();
  }

  function handleWordClick(word, idx, sentenceIdx, e) {
    e.stopPropagation();
    if (activeWord?.sentenceIdx === sentenceIdx && activeWord?.idx === idx) {
      activeWord = null;
    } else {
      activeWord = { word, idx, sentenceIdx };
    }
  }

  async function setWordStatus(token, newStatus) {
    try {
      await updateVocabWord(token, newStatus);
      if (activeWord) activeWord.word.status = newStatus;
      await loadTranscript();
      addToast(`"${token}" → ${newStatus}`, 'success');
    } catch (err) {
      addToast(`Failed: ${err.message}`, 'error');
    }
  }

  function navigate(dir) {
    const next = activeSentenceIdx + dir;
    if (next >= 0 && next < sentences.length) {
      activeSentenceIdx = next;
      document.getElementById(`s-${next}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }

  function handleKeydown(e) {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
    switch (e.key) {
      case 't': case 'T': showTranslation = !showTranslation; break;
      case 'r': case 'R': showRuby = !showRuby; break;
      case 's': case 'S': case ' ':
        e.preventDefault();
        if (sentences[activeSentenceIdx]) playAudio(sentences[activeSentenceIdx]);
        break;
      case 'j': case 'J': case 'ArrowDown': case 'ArrowRight': navigate(1); break;
      case 'k': case 'K': case 'ArrowUp': case 'ArrowLeft': navigate(-1); break;
      case 'Escape': activeWord = null; showLegend = false; break;
      case '?': showLegend = !showLegend; e.preventDefault(); break;
    }
  }

  function closePopover() { activeWord = null; }

  function showInDictionary(token) {
    vocabSearchQuery.set(token);
    currentView.set('vocab');
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="transcript-view">
  <div class="transcript-toolbar">
    <span class="toolbar-info">{sentences.length} sentences</span>
    <div class="toolbar-actions">
      <button
        class="toolbar-btn"
        class:active={showTranslation}
        onclick={() => showTranslation = !showTranslation}
        title="Toggle translation (T)"
      >
        {showTranslation ? '📖 Hide translation' : '📖 Show translation'}
      </button>
      <button class="toolbar-btn" class:active={showRuby}
        onclick={() => showRuby = !showRuby} title="Toggle ruby annotations (R)">
        🎨 Ruby
      </button>
    </div>
  </div>

  {#if loading}
    <div class="loading-state">⏳ Loading transcript...</div>
  {:else if sentences.length === 0}
    <div class="empty-state">No sentences for this video yet.</div>
  {:else}
    <div class="sentence-list">
      {#each sentences as sentence, idx}
        <div
          id="s-{idx}"
          class="transcript-sentence"
          class:active={idx === activeSentenceIdx}
          onclick={() => activeSentenceIdx = idx}
          role="button"
          tabindex="0"
        >
          <span class="sentence-num">{idx + 1}</span>
          <div class="sentence-content">
            <!-- Chinese text with clickable words -->
            <div class="sentence-chinese">
              {#if showRuby && sentence.ruby?.length}
                <!-- Ruby annotation mode: character-level pinyin with tone colors -->
                {#each sentence.ruby as entry}
                  <ruby class="ruby-char">
                    {entry.char}<rt style="color: {TONE_COLORS[entry.tone] || '#9E9E9E'}">{entry.pinyin}</rt>
                  </ruby>
                {/each}
              {:else if sentence.words?.length}
                {#each sentence.words as word, widx}
                  <span
                    class="word-token word-{word.status}"
                    onclick={(e) => handleWordClick(word, widx, idx, e)}
                    role="button"
                    tabindex="0"
                  >
                    {word.token}
                  </span>
                {/each}
              {:else}
                {sentence.text}
              {/if}

              {#if sentence.has_audio}
                <button
                  class="play-btn"
                  onclick={(e) => { e.stopPropagation(); playAudio(sentence); }}
                  title="Replay audio (S/Space)"
                >▶</button>
              {/if}
            </div>

            <!-- Pinyin -->
            {#if sentence.pinyin}
              <div class="sentence-pinyin">{sentence.pinyin}</div>
            {/if}

            <!-- Translation (togglable) -->
            {#if showTranslation && sentence.translation_de}
              <div class="sentence-translation">{sentence.translation_de}</div>
            {/if}

            <!-- Frequency badge for unknown word -->
            {#if sentence.unknown_word && sentence.frequency_badge}
              <span class="freq-tag">{sentence.frequency_badge} {sentence.unknown_word} #{sentence.unknown_word_rank}</span>
            {/if}

            <!-- Status badge -->
            <span class="sentence-status status-{sentence.status}">{sentence.status}</span>
          </div>
        </div>
      {/each}
    </div>
  {/if}

  <!-- Word popover -->
  {#if activeWord}
    <div class="word-popover-overlay" onclick={closePopover} role="button" tabindex="0"></div>
    <div class="word-popover">
      <div class="popover-word">{activeWord.word.token}</div>
      <div class="popover-meta">
        {#if activeWord.word.hsk_level}
          <span class="hsk-badge hsk-{activeWord.word.hsk_level}">HSK{activeWord.word.hsk_level}</span>
        {/if}
        {#if activeWord.word.frequency_rank}
          <span class="freq-badge">#{activeWord.word.frequency_rank}</span>
        {/if}
      </div>
      <div class="popover-status-row">
        Status: <span class="status-badge-inline word-{activeWord.word.status}">{activeWord.word.status}</span>
      </div>
      <div class="popover-actions">
        <button
          class="popover-btn"
          onclick={() => setWordStatus(activeWord.word.token, 'known')}
          disabled={activeWord.word.status === 'known'}
        >✅ Mark known</button>
        <button
          class="popover-btn"
          onclick={() => setWordStatus(activeWord.word.token, 'learning')}
          disabled={activeWord.word.status === 'learning'}
        >📚 Mark learning</button>
        <button
          class="popover-btn"
          onclick={() => setWordStatus(activeWord.word.token, 'unknown')}
          disabled={activeWord.word.status === 'unknown'}
        >❓ Mark unknown</button>
        <button
          class="popover-btn"
          onclick={() => showImagePicker = true}
        >🖼️ Search images</button>
        <button
          class="popover-btn"
          onclick={() => showInDictionary(activeWord.word.token)}
        >📋 Show in dictionary</button>
      </div>
      <button class="popover-close" onclick={closePopover}>✕</button>
    </div>
  {/if}

  <!-- Image picker modal -->
  {#if showImagePicker && activeWord}
    <ImagePicker
      word={activeWord.word.token}
      sentenceId={sentences[activeWord.sentenceIdx]?.id}
      onClose={() => showImagePicker = false}
    />
  {/if}

  <!-- Keyboard shortcuts legend bar -->
  {#if showLegend}
    <div class="shortcuts-bar">
      <span><kbd>T</kbd> Translate</span>
      <span><kbd>R</kbd> Ruby</span>
      <span><kbd>S</kbd> / <kbd>Space</kbd> Replay</span>
      <span><kbd>↓→J</kbd> Next</span>
      <span><kbd>↑←K</kbd> Previous</span>
      <span><kbd>Esc</kbd> Close</span>
      <span><kbd>?</kbd> Legend</span>
      <button class="shortcuts-close" onclick={() => showLegend = false}>✕</button>
    </div>
  {/if}
</div>

<style>
  .transcript-view {
    display: flex;
    flex-direction: column;
    height: 100%;
    position: relative;
  }
  .transcript-toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 24px;
    border-bottom: 1px solid var(--border);
    background: var(--bg-sidebar);
    position: sticky;
    top: 0;
    z-index: 10;
  }
  .toolbar-info {
    font-size: 0.85rem;
    color: var(--text-secondary);
  }
  .toolbar-actions {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .toolbar-btn {
    padding: 5px 12px;
    background: none;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    color: var(--text-secondary);
    font-size: 0.8rem;
    cursor: pointer;
    transition: all 0.15s;
  }
  .toolbar-btn:hover {
    color: var(--text);
    border-color: var(--text-secondary);
  }
  .toolbar-btn.active {
    color: var(--accent);
    border-color: var(--accent);
    background: rgba(233, 69, 96, 0.1);
  }
  .loading-state, .empty-state {
    text-align: center;
    color: var(--text-secondary);
    padding: 80px 0;
  }
  .sentence-list {
    flex: 1;
    overflow-y: auto;
    padding: 16px 24px;
  }
  .transcript-sentence {
    display: flex;
    gap: 12px;
    padding: 12px 16px;
    margin-bottom: 8px;
    border: 1px solid transparent;
    border-radius: var(--radius);
    cursor: pointer;
    transition: background 0.15s, border-color 0.15s;
  }
  .transcript-sentence:hover {
    background: rgba(255, 255, 255, 0.03);
  }
  .transcript-sentence.active {
    background: rgba(233, 69, 96, 0.08);
    border-color: rgba(233, 69, 96, 0.3);
  }
  .sentence-num {
    color: var(--text-secondary);
    font-size: 0.75rem;
    min-width: 28px;
    text-align: right;
    padding-top: 4px;
    opacity: 0.5;
  }
  .sentence-content {
    flex: 1;
    min-width: 0;
  }
  .sentence-chinese {
    font-size: 1.2rem;
    line-height: 1.8;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 2px 6px;
  }

  /* Word tokens */
  .word-token {
    cursor: pointer;
    padding: 1px 4px;
    border-radius: 3px;
    transition: background 0.15s;
    user-select: none;
  }
  .word-token:hover {
    filter: brightness(1.2);
  }
  .word-known { color: var(--accent-green, #4ecca3); }
  .word-learning {
    color: #ffa726;
    border-bottom: 2px dotted #ffa726;
  }
  .word-unknown {
    color: var(--accent, #e94560);
    border-bottom: 2px dotted var(--accent, #e94560);
  }

  .play-btn {
    background: none;
    border: 1px solid var(--border);
    border-radius: 50%;
    width: 24px;
    height: 24px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    color: var(--text-secondary);
    font-size: 0.65rem;
    cursor: pointer;
    margin-left: 6px;
    flex-shrink: 0;
  }
  .play-btn:hover {
    color: var(--accent);
    border-color: var(--accent);
  }

  .sentence-pinyin {
    font-size: 0.85rem;
    color: var(--accent-green);
    font-style: italic;
    margin-top: 2px;
  }
  .sentence-translation {
    font-size: 0.9rem;
    color: var(--text-secondary);
    margin-top: 4px;
    padding-left: 8px;
    border-left: 2px solid var(--border);
  }
  .freq-tag {
    display: inline-block;
    font-size: 0.7rem;
    color: var(--text-secondary);
    margin-top: 4px;
    opacity: 0.7;
  }
  .sentence-status {
    display: inline-block;
    font-size: 0.65rem;
    padding: 1px 6px;
    border-radius: 3px;
    margin-left: 6px;
    vertical-align: middle;
    text-transform: uppercase;
  }
  .status-i1 { background: rgba(233, 69, 96, 0.2); color: var(--accent); }
  .status-i0 { background: rgba(78, 204, 163, 0.2); color: var(--accent-green); }
  .status-kept { background: rgba(78, 204, 163, 0.3); color: var(--accent-green); }
  .status-stashed { background: rgba(255, 255, 255, 0.05); color: var(--text-secondary); }
  .status-deleted { background: rgba(255, 255, 255, 0.05); color: var(--text-secondary); text-decoration: line-through; }

  /* Word popover */
  .word-popover-overlay {
    position: fixed;
    inset: 0;
    z-index: 90;
  }
  .word-popover {
    position: fixed;
    left: 50%;
    top: 50%;
    transform: translate(-50%, -50%);
    z-index: 100;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px 20px;
    min-width: 220px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.5);
  }
  .popover-word {
    font-size: 1.3rem;
    font-weight: 600;
    margin-bottom: 8px;
  }
  .popover-meta {
    display: flex;
    gap: 6px;
    margin-bottom: 8px;
  }
  .hsk-badge {
    padding: 1px 6px;
    border-radius: 3px;
    font-size: 0.7rem;
    font-weight: 700;
    background: rgba(100, 149, 237, 0.25);
    color: #6495ed;
  }
  .freq-badge {
    padding: 1px 6px;
    border-radius: 3px;
    font-size: 0.7rem;
    background: rgba(255, 255, 255, 0.08);
    color: var(--text-secondary);
  }
  .popover-status-row {
    font-size: 0.8rem;
    color: var(--text-secondary);
    margin-bottom: 10px;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .status-badge-inline {
    padding: 1px 8px;
    border-radius: 3px;
    font-size: 0.75rem;
    font-weight: 600;
  }
  .status-badge-inline.word-known { background: rgba(78, 204, 163, 0.2); }
  .status-badge-inline.word-learning { background: rgba(255, 167, 38, 0.2); }
  .status-badge-inline.word-unknown { background: rgba(233, 69, 96, 0.2); }
  .popover-actions {
    display: flex;
    flex-direction: column;
    gap: 5px;
  }
  .popover-btn {
    padding: 6px 12px;
    border: 1px solid var(--border);
    border-radius: 4px;
    background: transparent;
    color: var(--text);
    font-size: 0.8rem;
    cursor: pointer;
    text-align: left;
  }
  .popover-btn:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.08);
  }
  .popover-btn:disabled {
    opacity: 0.4;
    cursor: default;
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
  }

  /* Shortcuts legend bar */
  .shortcuts-bar {
    position: fixed;
    bottom: 0;
    left: 320px;
    right: 0;
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 8px 24px;
    background: var(--bg-sidebar);
    border-top: 1px solid var(--border);
    font-size: 0.75rem;
    color: var(--text-secondary);
    z-index: 50;
  }
  .shortcuts-bar kbd {
    padding: 1px 5px;
    border: 1px solid var(--border);
    border-radius: 3px;
    font-family: monospace;
    font-size: 0.7rem;
    background: rgba(255, 255, 255, 0.05);
  }
  .shortcuts-close {
    margin-left: auto;
    background: none;
    border: none;
    color: var(--text-secondary);
    cursor: pointer;
  }
</style>
