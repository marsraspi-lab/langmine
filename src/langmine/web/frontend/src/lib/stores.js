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

export const selectedVideo = derived(
  [videos, selectedVideoId],
  ([$videos, $selectedVideoId]) =>
    $videos.find(v => v.id === $selectedVideoId) || null
);

export async function loadVideos() {
  const data = await api.listVideos();
  videos.set(data.videos);
}

export async function selectVideo(id) {
  selectedVideoId.set(id);
  currentFilter.set('all');
  await loadSentences(id, 'all');
}

export async function loadSentences(videoId, filter) {
  const data = await api.getSentences(videoId, filter);
  sentences.set(data.sentences);
}

export async function mineVideo(url) {
  mining.set(true);
  mineStatus.set('⏳ Mining...');
  try {
    const { ok, data } = await api.mineVideo(url);
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
