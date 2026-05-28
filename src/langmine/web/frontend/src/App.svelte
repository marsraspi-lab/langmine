<script>
  import { onMount } from 'svelte';
  import Sidebar from './lib/Sidebar.svelte';
  import CardList from './lib/CardList.svelte';
  import { loadVideos, selectedVideoId, sentences } from './lib/stores.js';

  onMount(() => {
    loadVideos();
  });
</script>

<div class="app-layout">
  <Sidebar />
  <main class="main-content">
    {#if $selectedVideoId}
      <CardList videoId={$selectedVideoId} />
    {:else}
      <div class="empty-state">
        Select a video from the sidebar to view sentences.
      </div>
    {/if}
  </main>
</div>

<style>
  .app-layout {
    display: flex;
    height: 100vh;
  }
  .main-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow-y: auto;
  }
  .empty-state {
    text-align: center;
    color: var(--text-secondary);
    padding: 80px 0;
    font-size: 1rem;
  }
</style>
