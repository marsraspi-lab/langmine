<script>
  import { videos, selectedVideoId, mineStatus, mining, selectVideo, mineVideo,
    exportStatus, exporting, exportAnki } from './stores.js';

  let urlInput = $state('');
  let forceUpdateModel = $state(false);

  async function handleMine() {
    const url = urlInput.trim();
    if (!url) {
      mineStatus.set('Enter a YouTube URL.');
      return;
    }
    await mineVideo(url);
    urlInput = '';
  }

  function handleKeydown(e) {
    if (e.key === 'Enter') handleMine();
  }
</script>

<aside class="sidebar">
  <div class="sidebar-header">
    <h1>⛏️ LangMine</h1>
  </div>

  <div class="mine-form">
    <input
      type="text"
      placeholder="YouTube URL..."
      bind:value={urlInput}
      onkeydown={handleKeydown}
      disabled={$mining}
    />
    <button onclick={handleMine} disabled={$mining}>
      {$mining ? '⏳' : 'Mine'}
    </button>
    {#if $mineStatus}
      <div class="mine-status">{$mineStatus}</div>
    {/if}
  </div>

  <nav class="video-list">
    {#if $videos.length === 0}
      <div class="empty-videos">No videos yet. Paste a YouTube URL above.</div>
    {:else}
      {#each $videos as video (video.id)}
        <button
          class="video-item"
          class:active={$selectedVideoId === video.id}
          onclick={() => selectVideo(video.id)}
        >
          <div class="video-title">{video.title || video.youtube_id}</div>
          <div class="video-meta">
            {video.total_sentences} sentences
            {#if video.i1_count > 0}
              <span class="count-i1">🔥{video.i1_count}</span>
            {/if}
            {#if video.kept_count > 0}
              <span class="count-kept">✅{video.kept_count}</span>
            {/if}
          </div>
        </button>
      {/each}
    {/if}
  </nav>

  {#if $videos.length > 0}
    <div class="export-section">
      <button
        class="export-btn"
        onclick={() => exportAnki(null, forceUpdateModel)}
        disabled={$exporting}
      >
        {$exporting ? '⏳' : '📦'} Export to Anki
      </button>
      <label class="force-update-label">
        <input
          type="checkbox"
          bind:checked={forceUpdateModel}
          disabled={$exporting}
        />
        ⚡ Update card templates
      </label>
      {#if $exportStatus}
        <div class="export-status">{$exportStatus}</div>
      {/if}
    </div>
  {/if}
</aside>

<style>
  .sidebar {
    width: 320px;
    min-width: 320px;
    background: var(--bg-sidebar);
    border-right: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    overflow-y: auto;
    height: 100vh;
  }
  .sidebar-header {
    padding: 20px;
    border-bottom: 1px solid var(--border);
  }
  .sidebar-header h1 {
    font-size: 1.3rem;
    margin: 0;
  }
  .mine-form {
    padding: 16px 20px;
    border-bottom: 1px solid var(--border);
  }
  .mine-form input {
    width: 100%;
    padding: 8px 12px;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    color: var(--text);
    font-size: 0.9rem;
    margin-bottom: 8px;
    box-sizing: border-box;
  }
  .mine-form input:focus {
    outline: none;
    border-color: var(--accent);
  }
  .mine-form button {
    width: 100%;
    padding: 8px;
    background: var(--accent);
    color: white;
    border: none;
    border-radius: var(--radius);
    font-size: 0.9rem;
    cursor: pointer;
  }
  .mine-form button:hover:not(:disabled) {
    opacity: 0.9;
  }
  .mine-form button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .mine-status {
    font-size: 0.8rem;
    color: var(--text-secondary);
    margin-top: 8px;
    line-height: 1.4;
  }
  .video-list {
    flex: 1;
    overflow-y: auto;
  }
  .empty-videos {
    padding: 20px;
    color: var(--text-secondary);
    font-size: 0.85rem;
  }
  .video-item {
    display: block;
    width: 100%;
    padding: 12px 20px;
    border: none;
    border-bottom: 1px solid var(--border);
    background: none;
    color: var(--text);
    text-align: left;
    cursor: pointer;
    transition: background 0.15s;
    font-size: inherit;
  }
  .video-item:hover {
    background: rgba(255, 255, 255, 0.05);
  }
  .video-item.active {
    background: rgba(233, 69, 96, 0.15);
    border-left: 3px solid var(--accent);
  }
  .video-title {
    font-size: 0.85rem;
    font-weight: 600;
    margin-bottom: 4px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .video-meta {
    font-size: 0.75rem;
    color: var(--text-secondary);
  }
  .count-i1 {
    color: var(--accent);
    margin-left: 6px;
  }
  .count-kept {
    color: var(--accent-green);
    margin-left: 6px;
  }
  .export-section {
    padding: 12px 20px;
    border-top: 1px solid var(--border);
  }
  .export-btn {
    width: 100%;
    padding: 10px;
    background: var(--accent-green);
    color: white;
    border: none;
    border-radius: var(--radius);
    font-size: 0.9rem;
    cursor: pointer;
    font-weight: 600;
  }
  .export-btn:hover:not(:disabled) {
    opacity: 0.9;
  }
  .export-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .export-status {
    font-size: 0.8rem;
    color: var(--text-secondary);
    margin-top: 8px;
    line-height: 1.4;
  }
  .force-update-label {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.75rem;
    color: var(--text-secondary);
    margin-top: 8px;
    cursor: pointer;
  }
  .force-update-label input {
    accent-color: var(--accent);
  }
</style>
