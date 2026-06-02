<script>
  import { onMount } from 'svelte';
  import Sidebar from './lib/Sidebar.svelte';
  import CardList from './lib/CardList.svelte';
  import { app, loadVideos, removeToast, toggleTheme, loadConfig, loadLanguages, selectLanguage, loadWordStatuses } from './lib/stores.svelte.js';
  import SettingsPage from './lib/SettingsPage.svelte';
  import VocabPage from './lib/VocabPage.svelte';

  onMount(() => {
    loadVideos();
    loadConfig();
    loadLanguages();
    loadWordStatuses();
  });

  // Theme persistence (moved from stores.svelte.js — module-level $effect
  // is not supported by the Rolldown/Vite bundler)
  $effect(() => {
    document.documentElement.setAttribute('data-theme', app.theme);
    localStorage.setItem('langmine-theme', app.theme);
  });
</script>

<div class="app-layout">
  <header class="top-bar">
    <span class="brand">⛏️ LangMine</span>
    <div class="lang-selector">
      <select value={app.currentLanguage} onchange={(e) => selectLanguage(e.target.value)}>
        {#each app.languages as lang (lang.code)}
          <option value={lang.code}>{lang.name}</option>
        {/each}
      </select>
    </div>
    <div class="top-actions">
      <button class="nav-btn" class:active={app.currentView === 'curation'} onclick={() => app.currentView = 'curation'}>
        📹 Curation
      </button>
      <button class="nav-btn" class:active={app.currentView === 'settings'} onclick={() => app.currentView = 'settings'}>
        ⚙️ Settings
      </button>
      <button class="nav-btn" class:active={app.currentView === 'vocab'} onclick={() => app.currentView = 'vocab'}>
        📚 Vocabulary
      </button>
      <button class="theme-btn" onclick={toggleTheme} title="Toggle theme">
        {app.theme === 'dark' ? '☀️' : '🌙'}
      </button>
    </div>
  </header>

  <div class="app-body">
    {#if app.currentView === 'settings'}
      <div class="settings-container">
        <SettingsPage />
      </div>
    {:else if app.currentView === 'vocab'}
      <div class="settings-container">
        <VocabPage />
      </div>
    {:else}
      <Sidebar />
      <main class="main-content">
        {#if app.selectedVideoId}
          <CardList videoId={app.selectedVideoId} />
        {:else}
          <div class="empty-state">
            <p>No video selected.</p>
            <p class="hint">Choose a video from the sidebar or mine a new one.</p>
          </div>
        {/if}
      </main>
    {/if}
  </div>
</div>

<!-- Toast notifications -->
<div class="toast-container">
  {#each app.toasts as toast (toast.id)}
    <div class="toast toast-{toast.type}" role="button" tabindex="0" onclick={() => removeToast(toast.id)} onkeydown={(e) => e.key === 'Enter' && removeToast(toast.id)}>
      {toast.message}
    </div>
  {/each}
</div>

<style>
  .app-layout {
    display: flex;
    flex-direction: column;
    height: 100vh;
  }
  .top-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 24px;
    border-bottom: 1px solid var(--border);
    background: var(--bg-sidebar);
  }
  .brand {
    font-weight: 700;
    font-size: 1.1rem;
    color: var(--accent);
  }
  .lang-selector select {
    padding: 4px 10px;
    background: var(--bg-sidebar);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    color: var(--text);
    font-size: 0.85rem;
    cursor: pointer;
  }
  .lang-selector select:hover {
    border-color: var(--accent);
  }
  .top-actions {
    display: flex;
    gap: 8px;
    align-items: center;
  }
  .nav-btn {
    padding: 6px 14px;
    background: none;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    color: var(--text-secondary);
    font-size: 0.85rem;
    cursor: pointer;
    transition: color 0.15s, border-color 0.15s;
  }
  .nav-btn:hover {
    color: var(--text);
  }
  .nav-btn.active {
    color: var(--accent);
    border-color: var(--accent);
  }
  .theme-btn {
    padding: 6px 10px;
    background: none;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    font-size: 1rem;
    cursor: pointer;
    transition: background 0.15s;
  }
  .theme-btn:hover {
    background: rgba(255, 255, 255, 0.05);
  }
  .app-body {
    display: flex;
    flex: 1;
    overflow: hidden;
  }
  .main-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow-y: auto;
  }
  .settings-container {
    flex: 1;
    overflow-y: auto;
    padding: 24px;
  }
  .empty-state {
    text-align: center;
    color: var(--text-secondary);
    padding: 80px 0;
    font-size: 1rem;
  }
  .hint {
    font-size: 0.85rem;
    opacity: 0.7;
    margin-top: 8px;
  }

  /* Toasts */
  .toast-container {
    position: fixed;
    bottom: 20px;
    right: 20px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    z-index: 1000;
  }
  .toast {
    padding: 12px 20px;
    border-radius: var(--radius);
    color: #fff;
    font-size: 0.9rem;
    cursor: pointer;
    animation: slideIn 0.2s ease;
    max-width: 360px;
  }
  .toast-success {
    background: #2e7d32;
  }
  .toast-error {
    background: #c62828;
  }
  .toast-info {
    background: #1565c0;
  }
  @keyframes slideIn {
    from { transform: translateX(100%); opacity: 0; }
    to { transform: translateX(0); opacity: 1; }
  }
</style>
