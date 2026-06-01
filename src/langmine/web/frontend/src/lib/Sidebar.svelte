<script>
  import { videos, selectedVideoId, mineStatus, mining, selectVideo, mineVideo,
    exportStatus, exporting, exportAnki, deleteVideo } from './stores.js';
  import { previewVideo, fetchSubtitleInfo } from './api.js';
  import PreviewPanel from './PreviewPanel.svelte';

  let urlInput = $state('');
  let forceUpdateModel = $state(false);
  let clozeMode = $state(false);
  /** @type {File|null} */
  let transcriptFile = $state(null);
  let dragOver = $state(false);

  // Preview state
  let previewLoading = $state(false);
  let previewData = $state(null);
  let previewError = $state('');

  // Subtitle discovery state (M25)
  let subInfo = $state(null);
  let subLoading = $state(false);
  let subCheckTimer = null;
  let selectedSubLang = $state('');

  // M26: Sorted subtitle lists for optgroup dropdown
  let allSubs = $derived(subInfo?.subtitles ?? []);
  let sortedManualSubs = $derived(
    allSubs.filter(s => s.kind === 'manual').sort((a, b) => a.language_name.localeCompare(b.language_name))
  );
  let sortedAutoSubs = $derived(
    allSubs.filter(s => s.kind === 'auto').sort((a, b) => a.language_name.localeCompare(b.language_name))
  );
  let hasManualSubs = $derived(sortedManualSubs.length > 0);
  let hasAutoSubs = $derived(sortedAutoSubs.length > 0);

  async function handleMine() {
    const url = urlInput.trim();
    if (!url) {
      mineStatus.set('Enter a YouTube URL.');
      return;
    }
    await mineVideo(url, transcriptFile, selectedSubLang);
    urlInput = '';
    transcriptFile = null;
    // Reset the file input
    const fileInput = document.getElementById('transcript-file-input');
    if (fileInput) fileInput.value = '';
  }

  function handleKeydown(e) {
    if (e.key === 'Enter') handleMine();
  }

  function handleFileChange(e) {
    transcriptFile = e.target.files[0] || null;
  }

  function handleDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
    dragOver = true;
  }

  function handleDragLeave(e) {
    e.preventDefault();
    dragOver = false;
  }

  function handleDrop(e) {
    e.preventDefault();
    dragOver = false;
    const file = e.dataTransfer.files[0];
    if (file && (file.name.endsWith('.srt') || file.name.endsWith('.vtt'))) {
      transcriptFile = file;
    }
  }

  async function handlePreview() {
    const url = urlInput.trim();
    if (!url) {
      previewError = 'Enter a YouTube URL.';
      return;
    }
    previewLoading = true;
    previewError = '';
    previewData = null;
    try {
      const result = await previewVideo(url);
      if (result.ok) {
        previewData = result.data;
      } else {
        previewError = result.data?.error || `Preview failed (${result.status})`;
      }
    } catch (err) {
      previewError = `Preview failed: ${err.message}`;
    } finally {
      previewLoading = false;
    }
  }

  function handleUrlInput() {
    subInfo = null;
    clearTimeout(subCheckTimer);
    const url = urlInput.trim();
    if (!url || url.length < 20) return;

    subCheckTimer = setTimeout(async () => {
      subLoading = true;
      try {
        const result = await fetchSubtitleInfo(url);
        if (result.ok) {
          subInfo = result.data;
          // Auto-select first manual sub, fall back to first auto
          const firstChoice = sortedManualSubs[0] ?? sortedAutoSubs[0];
          if (firstChoice) selectedSubLang = firstChoice.language_code;
        }
      } catch (e) {
        // best-effort — ignore failures
      } finally {
        subLoading = false;
      }
    }, 800);
  }
</script>

<aside class="sidebar">
  <div class="sidebar-header">
    <h1>⛏️ LangMine</h1>
  </div>

  <div class="mine-form"
       class:drag-over={dragOver}
       ondragover={handleDragOver}
       ondragleave={handleDragLeave}
       ondrop={handleDrop}
  >
    <input
      type="text"
      placeholder="YouTube URL..."
      bind:value={urlInput}
      oninput={handleUrlInput}
      onkeydown={handleKeydown}
      disabled={$mining}
    />
    {#if subLoading}
      <div class="subtitle-chip loading">⏳ Checking subtitles…</div>
    {:else if subInfo && subInfo.available}
      {#if hasManualSubs && sortedManualSubs.length === 1 && sortedAutoSubs.length === 0}
        {@const s = sortedManualSubs[0]}
        <div class="subtitle-chip manual" title={s.language_name}>
          ✅ {s.language_name} (manual)
        </div>
      {:else}
        <div class="subtitle-chip manual sub-lang-row">
          <span>✅</span>
          <select bind:value={selectedSubLang} class="sub-lang-select">
            {#if hasManualSubs}
              <optgroup label="── Manual subtitles ──">
                {#each sortedManualSubs as s}
                  <option value={s.language_code}>{s.language_name} (manual)</option>
                {/each}
              </optgroup>
            {/if}
            {#if hasAutoSubs}
              <optgroup label="── Auto-generated captions ──">
                {#each sortedAutoSubs as s}
                  <option value={s.language_code}>{s.language_name} (auto)</option>
                {/each}
              </optgroup>
            {/if}
          </select>
        </div>
      {/if}
    {:else if subInfo && !subInfo.available}
      <div class="subtitle-chip none">❌ No subtitles available</div>
    {/if}
    <label class="file-upload-label" class:has-file={transcriptFile !== null}>
      <span>{transcriptFile ? `📄 ${transcriptFile.name}` : '📂 Transcript .srt / .vtt (optional)'}</span>
      <input
        id="transcript-file-input"
        type="file"
        accept=".srt,.vtt"
        onchange={handleFileChange}
        disabled={$mining}
      />
    </label>
    <button onclick={handleMine} disabled={$mining}>
      {$mining ? '⏳' : 'Mine'}
    </button>
    <button class="preview-btn" onclick={handlePreview} disabled={previewLoading}>
      {previewLoading ? '⏳' : '🔍'} Preview
    </button>
    {#if $mineStatus}
      <div class="mine-status">{$mineStatus}</div>
    {/if}
    {#if previewError}
      <div class="mine-status preview-error">{previewError}</div>
    {/if}
  </div>

  <PreviewPanel data={previewData} />

  <nav class="video-list">
    {#if $videos.length === 0}
      <div class="empty-videos">No videos yet. Paste a YouTube URL above.</div>
    {:else}
      {#each $videos as video (video.id)}
        <div class="video-row">
          <button
            class="video-item"
            class:active={$selectedVideoId === video.id}
            onclick={() => selectVideo(video.id)}
          >
            <div class="video-title" title="{video.title || video.youtube_id} — {video.youtube_id}">
              {#if video.title && video.title !== video.youtube_id}
                {(video.title.length > 35 ? video.title.slice(0, 35) + '…' : video.title)}
              {:else}
                {video.youtube_id}
              {/if}
            </div>
            <div class="video-meta">
              {video.total_sentences} sentences
              {#if video.i1_count > 0}
                <span class="count-i1">🔥{video.i1_count}</span>
              {/if}
              {#if video.kept_count > 0}
                <span class="count-kept">✅{video.kept_count}</span>
              {/if}
              {#if video.subtitle_kind === 'auto'}
                <span class="sub-badge auto">🤖 auto</span>
              {:else if video.subtitle_kind === 'manual'}
                <span class="sub-badge manual">✍️ manual</span>
              {/if}
            </div>
          </button>
          <button
            class="delete-video-btn"
            onclick={(e) => { e.stopPropagation(); deleteVideo(video.id); }}
            title="Delete video"
          >🗑️</button>
        </div>
      {/each}
    {/if}
  </nav>

  {#if $videos.length > 0}
    <div class="export-section">
      <button
        class="export-btn"
        onclick={() => exportAnki(null, forceUpdateModel, clozeMode ? 'cloze' : 'basic')}
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
      <label class="force-update-label">
        <input
          type="checkbox"
          bind:checked={clozeMode}
          disabled={$exporting}
        />
        🕳️ Cloze deletion cards
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
    transition: background 0.15s, border-color 0.15s;
  }
  .mine-form.drag-over {
    background: rgba(233, 69, 96, 0.08);
    border-color: var(--accent);
    outline: 2px dashed var(--accent);
    outline-offset: -6px;
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
  .file-upload-label {
    display: block;
    padding: 8px 12px;
    background: var(--bg);
    border: 1px dashed var(--border);
    border-radius: var(--radius);
    color: var(--text-secondary);
    font-size: 0.8rem;
    margin-bottom: 8px;
    cursor: pointer;
    text-align: center;
    transition: border-color 0.15s;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }
  .file-upload-label:hover {
    border-color: var(--accent);
    color: var(--text);
  }
  .file-upload-label.has-file {
    border-style: solid;
    border-color: var(--accent-green);
    color: var(--text);
  }
  .file-upload-label input[type="file"] {
    display: none;
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
  .subtitle-chip {
    font-size: 0.75rem;
    padding: 4px 8px;
    border-radius: 4px;
    margin-bottom: 8px;
  }
  .subtitle-chip.manual { background: rgba(76, 175, 80, 0.15); color: #66bb6a; }
  .subtitle-chip.auto  { background: rgba(255, 152, 0, 0.15); color: #ffa726; }
  .subtitle-chip.none  { background: rgba(244, 67, 54, 0.15); color: #ef5350; }
  .subtitle-chip.loading { background: rgba(255,255,255,0.05); color: var(--text-secondary); }
  .sub-lang-row {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .sub-lang-select {
    flex: 1;
    background: transparent;
    border: none;
    color: inherit;
    font-size: inherit;
    font-family: inherit;
    cursor: pointer;
    outline: none;
  }
  .sub-lang-select option {
    background: var(--bg);
    color: var(--text);
  }
  .preview-btn {
    width: 100%;
    padding: 8px;
    background: var(--bg);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    font-size: 0.9rem;
    cursor: pointer;
    margin-top: 6px;
  }
  .preview-btn:hover:not(:disabled) {
    border-color: var(--accent);
    background: rgba(255, 255, 255, 0.05);
  }
  .preview-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .preview-error {
    color: var(--accent);
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
  .video-row {
    display: flex;
    align-items: stretch;
    border-bottom: 1px solid var(--border);
  }
  .video-row .video-item {
    border-bottom: none;
    flex: 1;
  }
  .delete-video-btn {
    flex-shrink: 0;
    width: 36px;
    border: none;
    background: none;
    color: var(--text-secondary);
    cursor: pointer;
    font-size: 0.85rem;
    opacity: 0;
    transition: opacity 0.15s, color 0.15s;
  }
  .video-row:hover .delete-video-btn {
    opacity: 0.6;
  }
  .delete-video-btn:hover {
    opacity: 1 !important;
    color: var(--accent);
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
