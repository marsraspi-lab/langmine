<script>
  import { fetchVocab, fetchVocabWord, updateVocabWord } from './api.js';
  import { addToast } from './stores.js';

  let words = $state([]);
  let total = $state(0);
  let page = $state(1);
  let perPage = 200;
  let statusFilter = $state(null); // null = all, 'known', 'learning'
  let searchQuery = $state('');
  let loading = $state(false);
  let loadingMore = $state(false);
  let error = $state(null);

  // Detail panel state
  let selectedWord = $state(null);
  let wordDetail = $state(null);
  let detailLoading = $state(false);
  let detailSentences = $state([]);

  // Search debounce
  let searchTimeout = $state(null);

  // Derived
  let hasMore = $derived(words.length < total);

  async function loadWords(reset = true) {
    if (reset) {
      page = 1;
      words = [];
    }
    loading = true;
    error = null;
    try {
      const data = await fetchVocab(page, statusFilter, searchQuery || null, 'frequency');
      if (reset) {
        words = data.words;
      } else {
        words = [...words, ...data.words];
      }
      total = data.total;
    } catch (err) {
      error = err.message;
      addToast(`Failed to load vocabulary: ${err.message}`, 'error');
    } finally {
      loading = false;
      loadingMore = false;
    }
  }

  async function loadMore() {
    if (loadingMore || !hasMore) return;
    loadingMore = true;
    page += 1;
    await loadWords(false);
  }

  function onSearchInput(e) {
    searchQuery = e.target.value;
    if (searchTimeout) clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
      loadWords(true);
    }, 300);
  }

  function setStatusFilter(status) {
    statusFilter = status;
    loadWords(true);
  }

  async function selectWord(word) {
    if (selectedWord && selectedWord.word === word.word) {
      // Deselect
      selectedWord = null;
      wordDetail = null;
      detailSentences = [];
      return;
    }
    selectedWord = word;
    detailLoading = true;
    wordDetail = null;
    detailSentences = [];
    try {
      const data = await fetchVocabWord(word.word);
      wordDetail = data.word;
      detailSentences = data.sentences || [];
    } catch (err) {
      addToast(`Failed to load word detail: ${err.message}`, 'error');
    } finally {
      detailLoading = false;
    }
  }

  async function toggleDetailStatus(newStatus) {
    if (!selectedWord || !wordDetail) return;
    try {
      const result = await updateVocabWord(selectedWord.word, newStatus);
      if (result.ok || result.status) {
        wordDetail.status = newStatus;
        // Update in list too
        const idx = words.findIndex(w => w.word === selectedWord.word);
        if (idx >= 0) {
          words[idx].status = newStatus;
        }
        selectedWord.status = newStatus;
      }
    } catch (err) {
      addToast(`Failed to update word: ${err.message}`, 'error');
    }
  }

  function freqBadge(rank) {
    if (rank === null || rank === undefined) return null;
    if (rank <= 500) return '🔥';
    if (rank <= 3000) return '⭐';
    return '💎';
  }

  function statusEmoji(status) {
    if (status === 'known') return '🟢';
    if (status === 'learning') return '🟡';
    return '🔴';
  }

  function statusLabel(status) {
    return status || 'unknown';
  }

  // Initial load
  loadWords(true);

  let prevFilter = $derived(statusFilter);
  let prevSearch = $derived(searchQuery);
</script>

<div class="vocab-page">
  <h2>📚 Vocabulary</h2>

  <!-- Search bar -->
  <div class="vocab-toolbar">
    <div class="search-box">
      <span class="search-icon">🔍</span>
      <input
        type="text"
        placeholder="Search by word or pinyin..."
        value={searchQuery}
        oninput={onSearchInput}
        class="search-input"
      />
    </div>
  </div>

  <!-- Status filter tabs -->
  <div class="filter-tabs">
    <button
      class="filter-tab"
      class:active={statusFilter === null}
      onclick={() => setStatusFilter(null)}
    >
      All ({total})
    </button>
    <button
      class="filter-tab"
      class:active={statusFilter === 'known'}
      onclick={() => setStatusFilter('known')}
    >
      🟢 Known
    </button>
    <button
      class="filter-tab"
      class:active={statusFilter === 'learning'}
      onclick={() => setStatusFilter('learning')}
    >
      🟡 Learning
    </button>
    <button
      class="filter-tab"
      class:active={statusFilter === 'unknown'}
      onclick={() => setStatusFilter('unknown')}
    >
      🔴 Unknown
    </button>
  </div>

  <!-- Error state -->
  {#if error}
    <div class="error-state">{error}</div>
  {/if}

  <!-- Loading state -->
  {#if loading && words.length === 0}
    <div class="loading-state">⏳ Loading vocabulary...</div>
  {:else if words.length === 0 && !loading}
    <div class="empty-state">
      <p>No vocabulary words found.</p>
      <p class="hint">Mine some videos to build your vocabulary.</p>
    </div>
  {:else}
    <!-- Word list -->
    <div class="word-list">
      {#each words as word, idx}
        <div
          class="word-row"
          class:word-row-selected={selectedWord?.word === word.word}
          onclick={() => selectWord(word)}
          role="button"
          tabindex="0"
          onkeydown={(e) => e.key === 'Enter' && selectWord(word)}
        >
          <span class="word-status-emoji">{statusEmoji(word.status)}</span>
          <span class="word-text">{word.word}</span>
          {#if word.pinyin}
            <span class="word-pinyin">{word.pinyin}</span>
          {/if}
          <span class="word-badges">
            {#if word.frequency_rank}
              <span class="freq-badge" title="Frequency rank: {word.frequency_rank}">
                {freqBadge(word.frequency_rank)} #{word.frequency_rank}
              </span>
            {/if}
            {#if word.hsk_level}
              <span class="hsk-badge hsk-{word.hsk_level}">HSK{word.hsk_level}</span>
            {/if}
          </span>
        </div>

        <!-- Inline detail panel -->
        {#if selectedWord?.word === word.word}
          <div class="word-detail" transition:slide>
            {#if detailLoading}
              <div class="detail-loading">⏳ Loading...</div>
            {:else if wordDetail}
              <div class="detail-content">
                <div class="detail-header">
                  <span class="detail-word">{wordDetail.word}</span>
                  {#if wordDetail.pinyin}
                    <span class="detail-pinyin">{wordDetail.pinyin}</span>
                  {/if}
                </div>

                {#if wordDetail.definition_de}
                  <div class="detail-definitions">
                    <strong>Definition:</strong> {wordDetail.definition_de}
                  </div>
                {/if}

                <div class="detail-stats">
                  <span>Sentences: {wordDetail.sentence_count || 0}</span>
                  <span>Status: <span class="word-{wordDetail.status}">{statusLabel(wordDetail.status)}</span></span>
                  {#if wordDetail.frequency_rank}
                    <span>Frequency: #{wordDetail.frequency_rank}</span>
                  {/if}
                  {#if wordDetail.hsk_level}
                    <span>HSK Level: {wordDetail.hsk_level}</span>
                  {/if}
                </div>

                <div class="detail-actions">
                  <button
                    class="detail-btn btn-known"
                    onclick={() => toggleDetailStatus('known')}
                    disabled={wordDetail.status === 'known'}
                  >
                    ✅ Mark Known
                  </button>
                  <button
                    class="detail-btn btn-learning"
                    onclick={() => toggleDetailStatus('learning')}
                    disabled={wordDetail.status === 'learning'}
                  >
                    📚 Mark Learning
                  </button>
                  <button
                    class="detail-btn btn-unknown"
                    onclick={() => toggleDetailStatus('unknown')}
                    disabled={wordDetail.status === 'unknown'}
                  >
                    🔴 Mark Unknown
                  </button>
                </div>

                {#if detailSentences.length > 0}
                  <div class="detail-sentences">
                    <strong>Example sentences:</strong>
                    {#each detailSentences as s}
                      <div class="detail-sentence">{s.text || s.chinese}</div>
                    {/each}
                  </div>
                {/if}
              </div>
            {:else}
              <div class="detail-error">Failed to load word details.</div>
            {/if}
          </div>
        {/if}
      {/each}
    </div>

    <!-- Load more -->
    {#if hasMore}
      <div class="load-more-container">
        <button class="load-more-btn" onclick={loadMore} disabled={loadingMore}>
          {loadingMore ? '⏳ Loading...' : `Load more (${words.length} of ${total})`}
        </button>
      </div>
    {/if}
  {/if}
</div>

<style>
  .vocab-page {
    max-width: 900px;
    padding: 24px;
  }
  h2 {
    margin-bottom: 20px;
    color: var(--text);
  }

  /* Toolbar */
  .vocab-toolbar {
    margin-bottom: 16px;
  }
  .search-box {
    position: relative;
    max-width: 400px;
  }
  .search-icon {
    position: absolute;
    left: 12px;
    top: 50%;
    transform: translateY(-50%);
    font-size: 0.9rem;
    opacity: 0.6;
  }
  .search-input {
    width: 100%;
    padding: 10px 14px 10px 36px;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    color: var(--text);
    font-size: 0.95rem;
    font-family: inherit;
  }
  .search-input:focus {
    outline: none;
    border-color: var(--accent);
  }
  .search-input::placeholder {
    color: var(--text-secondary);
    opacity: 0.6;
  }

  /* Filter tabs */
  .filter-tabs {
    display: flex;
    gap: 4px;
    margin-bottom: 16px;
    flex-wrap: wrap;
  }
  .filter-tab {
    padding: 6px 16px;
    background: none;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    color: var(--text-secondary);
    font-size: 0.85rem;
    cursor: pointer;
    transition: color 0.15s, border-color 0.15s, background 0.15s;
  }
  .filter-tab:hover {
    color: var(--text);
    background: rgba(255, 255, 255, 0.04);
  }
  .filter-tab.active {
    color: var(--accent);
    border-color: var(--accent);
    background: rgba(233, 69, 96, 0.08);
  }

  /* States */
  .error-state {
    padding: 20px;
    color: var(--accent);
    background: rgba(233, 69, 96, 0.1);
    border-radius: var(--radius);
    text-align: center;
  }
  .loading-state, .empty-state {
    text-align: center;
    color: var(--text-secondary);
    padding: 60px 0;
    font-size: 1rem;
  }
  .hint {
    font-size: 0.85rem;
    opacity: 0.7;
    margin-top: 8px;
  }

  /* Word list */
  .word-list {
    border: 1px solid var(--border);
    border-radius: var(--radius);
    overflow: hidden;
  }
  .word-row {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 16px;
    cursor: pointer;
    border-bottom: 1px solid var(--border);
    transition: background 0.15s;
  }
  .word-row:last-child {
    border-bottom: none;
  }
  .word-row:hover {
    background: rgba(255, 255, 255, 0.03);
  }
  .word-row-selected {
    background: rgba(233, 69, 96, 0.06);
  }
  .word-status-emoji {
    font-size: 1rem;
    flex-shrink: 0;
  }
  .word-text {
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--text);
    min-width: 80px;
  }
  .word-pinyin {
    font-size: 0.85rem;
    color: var(--accent-green);
    font-style: italic;
  }
  .word-badges {
    margin-left: auto;
    display: flex;
    gap: 4px;
    align-items: center;
    flex-shrink: 0;
  }
  .freq-badge {
    display: inline-block;
    padding: 1px 6px;
    border-radius: 3px;
    font-size: 0.7rem;
    background: rgba(255, 255, 255, 0.08);
    color: var(--text-secondary);
  }
  .hsk-badge {
    display: inline-block;
    padding: 1px 6px;
    border-radius: 3px;
    font-size: 0.7rem;
    font-weight: 700;
    background: rgba(100, 149, 237, 0.25);
    color: #6495ed;
  }

  /* Detail panel */
  .word-detail {
    border-bottom: 1px solid var(--border);
    padding: 16px 20px;
    background: rgba(0, 0, 0, 0.15);
  }
  .detail-loading {
    text-align: center;
    color: var(--text-secondary);
    padding: 20px;
    font-size: 0.9rem;
  }
  .detail-error {
    color: var(--accent);
    font-size: 0.9rem;
  }
  .detail-header {
    display: flex;
    align-items: baseline;
    gap: 12px;
    margin-bottom: 12px;
  }
  .detail-word {
    font-size: 1.3rem;
    font-weight: 700;
    color: var(--text);
  }
  .detail-pinyin {
    font-size: 1rem;
    color: var(--accent-green);
    font-style: italic;
  }
  .detail-definitions {
    margin-bottom: 12px;
    font-size: 0.9rem;
    color: var(--text-secondary);
  }
  .detail-definitions ul {
    margin: 4px 0 0 0;
    padding-left: 20px;
  }
  .detail-definitions li {
    margin-bottom: 2px;
  }
  .detail-stats {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    margin-bottom: 12px;
    font-size: 0.85rem;
    color: var(--text-secondary);
  }
  .detail-actions {
    display: flex;
    gap: 8px;
    margin-bottom: 12px;
    flex-wrap: wrap;
  }
  .detail-btn {
    padding: 5px 14px;
    border: 1px solid var(--border);
    border-radius: 4px;
    background: transparent;
    color: var(--text);
    font-size: 0.8rem;
    cursor: pointer;
    transition: background 0.15s;
  }
  .detail-btn:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.08);
  }
  .detail-btn:disabled {
    opacity: 0.4;
    cursor: default;
  }
  .btn-known {
    border-color: var(--accent-green);
    color: var(--accent-green);
  }
  .btn-learning {
    border-color: #ffa726;
    color: #ffa726;
  }
  .btn-unknown {
    border-color: var(--accent);
    color: var(--accent);
  }
  .detail-sentences {
    font-size: 0.85rem;
    color: var(--text-secondary);
  }
  .detail-sentence {
    padding: 4px 0;
    border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  }

  /* Word status colors in detail */
  .word-known {
    color: var(--accent-green);
    font-weight: 600;
  }
  .word-learning {
    color: #ffa726;
    font-weight: 600;
  }
  .word-unknown {
    color: var(--accent);
    font-weight: 600;
  }

  /* Load more */
  .load-more-container {
    text-align: center;
    padding: 20px 0;
    margin-top: 8px;
  }
  .load-more-btn {
    padding: 10px 28px;
    background: none;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    color: var(--text-secondary);
    font-size: 0.9rem;
    cursor: pointer;
    transition: color 0.15s, border-color 0.15s, background 0.15s;
  }
  .load-more-btn:hover:not(:disabled) {
    color: var(--text);
    border-color: var(--accent);
    background: rgba(255, 255, 255, 0.04);
  }
  .load-more-btn:disabled {
    opacity: 0.5;
    cursor: default;
  }
</style>
