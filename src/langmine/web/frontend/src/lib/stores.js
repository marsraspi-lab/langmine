import { writable, derived } from 'svelte/store';
import { api } from './api.js';

/** @type {import('svelte/store').Writable<Array>} */
export const videos = writable([]);

/** @type {import('svelte/store').Writable<Array>} */
export const sentences = writable([]);

/** @type {import('svelte/store').Writable<number|null>} */
export const selectedVideoId = writable(null);

/** @type {import('svelte/store').Writable<string>} */
export const currentFilter = writable('all');

/** @type {import('svelte/store').Writable<string>} */
export const mineStatus = writable('');

/** @type {import('svelte/store').Writable<boolean>} */
export const mining = writable(false);

/** @type {import('svelte/store').Writable<string>} */
export const exportStatus = writable('');

/** @type {import('svelte/store').Writable<boolean>} */
export const exporting = writable(false);

/** @type {import('svelte/store').Writable<Array>} */
export const toasts = writable([]);

/** @type {import('svelte/store').Writable<Object>} */
export const config = writable({});

/** @type {import('svelte/store').Writable<string>} */
export const theme = writable(localStorage.getItem('langmine-theme') || 'dark');

/** @type {import('svelte/store').Writable<string>} */
export const currentView = writable('curation'); // 'curation' | 'settings'

/** @type {import('svelte/store').Writable<boolean>} */
export const readingMode = writable(false);

let toastId = 0;

export function addToast(message, type = 'info', duration = 4000) {
  const id = ++toastId;
  toasts.update(t => [...t, { id, message, type }]);
  if (duration > 0) {
    setTimeout(() => removeToast(id), duration);
  }
  return id;
}

export function removeToast(id) {
  toasts.update(t => t.filter(toast => toast.id !== id));
}

export const selectedVideo = derived(
  [videos, selectedVideoId],
  ([$videos, $selectedVideoId]) =>
    $videos.find(v => v.id === $selectedVideoId) || null
);

theme.subscribe(value => {
  if (typeof document !== 'undefined') {
    document.documentElement.setAttribute('data-theme', value);
    localStorage.setItem('langmine-theme', value);
  }
});

export async function loadVideos() {
  const data = await api.listVideos();
  videos.set(data.videos);
}

export async function selectVideo(id) {
  selectedVideoId.set(id);
  currentFilter.set('all');
  currentView.set('curation');
  await loadSentences(id, 'all');
}

export async function loadSentences(videoId, filter) {
  const data = await api.getSentences(videoId, filter);
  sentences.set(data.sentences);
}

export async function mineVideo(url, file = null) {
  mining.set(true);
  mineStatus.set('⏳ Mining...');
  try {
    const { ok, data } = await api.mineVideo(url, file);
    if (!ok) {
      mineStatus.set(`❌ ${data.error || 'Failed'}`);
      return null;
    }
    mineStatus.set(`✅ ${data.total_sentences} sentences, ${data.i1_count} i+1`);
    await loadVideos();
    if (data.video_id) {
      await selectVideo(data.video_id);
    }
    return data;
  } catch (err) {
    mineStatus.set(`❌ ${err.message}`);
    return null;
  } finally {
    mining.set(false);
  }
}

export async function keepSentence(id) {
  await api.updateSentence(id, 'kept');
  await refreshAfterAction();
}

export async function deleteSentence(id) {
  await api.updateSentence(id, 'deleted');
  await refreshAfterAction();
}

export async function markWordKnown(id) {
  await api.markWordKnown(id);
  await refreshAfterAction();
}

export async function updateSentenceField(id, fields) {
  try {
    await api.updateSentenceFields(id, fields);
    await refreshAfterAction();
    addToast('Saved ✓', 'success', 2000);
  } catch (err) {
    addToast(`Failed: ${err.message}`, 'error', 4000);
    throw err;
  }
}

export async function loadConfig() {
  try {
    const data = await api.getConfig();
    config.set(data);
  } catch (err) {
    console.error('Failed to load config:', err);
  }
}

export async function saveConfig(updates) {
  try {
    await api.updateConfig(updates);
    config.update(c => ({ ...c, ...updates }));
    addToast('Settings saved ✓', 'success', 2000);
  } catch (err) {
    addToast(`Failed to save: ${err.message}`, 'error');
  }
}

export function toggleTheme() {
  theme.update(t => t === 'dark' ? 'light' : 'dark');
}

async function refreshAfterAction() {
  await loadVideos();
  const vidId = $selectedVideoId;
  const filter = $currentFilter;
  if (vidId) {
    await loadSentences(vidId, filter);
  }
}

// Reactive store access for non-component usage
let $selectedVideoId;
let $currentFilter;
selectedVideoId.subscribe(v => $selectedVideoId = v);
currentFilter.subscribe(v => $currentFilter = v);

export async function exportAnki(videoId, forceUpdateModel = false) {
  exporting.set(true);
  exportStatus.set('⏳ Exporting...');
  try {
    const { ok, data } = await api.exportAnki(videoId, forceUpdateModel);
    if (!ok) throw new Error(data.error || 'Export failed');
    exportStatus.set(`✅ ${data.added} new, ${data.duplicates} duplicates`);
  } catch (err) {
    exportStatus.set(`❌ ${err.message}`);
  } finally {
    exporting.set(false);
  }
}
