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

/** @type {import('svelte/store').Writable<string>} */
export const vocabSearchQuery = writable('');  // pre-fill vocab search (M14)

/** @type {import('svelte/store').Writable<Array>} */
export const languages = writable([]);
/** @type {import('svelte/store').Writable<string>} */
export const currentLanguage = writable('zh');

// === New: word status stores (M19) ===

/** @type {import('svelte/store').Writable<Set<string>>} */
export const knownWords = writable(new Set());
/** @type {import('svelte/store').Writable<Set<string>>} */
export const learningWords = writable(new Set());
/** @type {import('svelte/store').Writable<Set<string>>} */
export const ignoredWords = writable(new Set());

/**
 * Move a word between status sets atomically.
 * Mutates all three sets in place, triggering reactive updates.
 */
export function setWordStatus(word, newStatus) {
  for (const [status, store] of Object.entries({
    known: knownWords,
    learning: learningWords,
    ignored: ignoredWords,
  })) {
    store.update(s => {
      const next = new Set(s);
      if (status === newStatus) next.add(word);
      else next.delete(word);
      return next;
    });
  }
}

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

export async function deleteVideo(id) {
  const { ok, data } = await api.deleteVideo(id);
  if (!ok) {
    addToast(data?.error || 'Failed to delete video', 'error');
    return false;
  }
  addToast('Video deleted', 'success', 2000);
  // If the deleted video is currently selected, deselect it
  if ($selectedVideoId === id) {
    selectedVideoId.set(null);
    sentences.set([]);
  }
  await loadVideos();
  return true;
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

// === Client-side sentence curation (M19) ===

/** Curated sentences with client-computed i+1/i0/stashed status
 *  and per-word status hashmaps for instant highlighting.
 *  Preserves user-action statuses: deleted, kept. */
export const curatedSentences = derived(
  [sentences, knownWords, learningWords, ignoredWords],
  ([$sentences, $knownWords, $learningWords, $ignoredWords]) => {
    return $sentences.map(s => {
      const tokens = (s.text_segmented || '').split(' / ').filter(Boolean);
      const unknown = tokens.filter(w =>
        !$knownWords.has(w) && !$ignoredWords.has(w)
      );
      const count = unknown.length;
      // User-action statuses (deleted, kept) take priority over computed
      let computed = count === 0 ? 'i0'
        : count === 1 ? 'i1'
        : count === 2 ? 'i2'
        : count === 3 ? 'i3'
        : 'stashed';
      if (s.status === 'deleted' || s.status === 'kept' || s.status === 'exported') {
        computed = s.status;
      }
      return {
        ...s,
        computedStatus: computed,
        wordStatuses: Object.fromEntries(tokens.map(w => [
          w,
          $knownWords.has(w) ? 'known'
            : $ignoredWords.has(w) ? 'ignored'
            : $learningWords.has(w) ? 'learning'
            : 'unknown'
        ])),
      };
    });
  }
);

export async function mineVideo(url, file = null) {
  mining.set(true);
  mineStatus.set('⏳ Mining...');
  try {
    let data;
    for await (const event of api.mineVideoStream(url, file)) {
      if (event.status) {
        mineStatus.set(`⏳ ${event.status}`);
      } else {
        data = event;  // final result
      }
    }
    if (!data) {
      mineStatus.set('❌ No result');
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
    if (data.source_language) {
      currentLanguage.set(data.source_language);
    }
  } catch (err) {
    console.error('Failed to load config:', err);
  }
}

export async function loadLanguages() {
  try {
    const data = await api.listLanguages();
    languages.set(data.languages);
  } catch (err) {
    console.error('Failed to load languages:', err);
  }
}

export async function selectLanguage(code) {
  if (code === $currentLanguageCode) return;
  try {
    await api.updateConfig({ source_language: code });
    currentLanguage.set(code);
    config.update(c => ({ ...c, source_language: code }));
    addToast(`Switched to ${code}`, 'info', 2000);
    await loadVideos();
    if ($selectedVideoId) {
      await loadSentences($selectedVideoId, $currentFilter);
    }
  } catch (err) {
    addToast(`Failed to switch language: ${err.message}`, 'error');
  }
}

// === M22: Reclassification + paginated "Add Sentences" ===

export let reclassifyOffset = 0;

export async function reclassifyAndLoad(videoId, offset = 0, limit = 50) {
  try {
    const res = await api.reclassifySentences(videoId, offset, limit);
    if (res.ok) {
      const { sentences: newSentences, total } = res.data;
      if (offset === 0) {
        sentences.set(newSentences);
      } else {
        sentences.update(existing => [...existing, ...newSentences]);
      }
      reclassifyOffset = offset + newSentences.length;
      return { hasMore: reclassifyOffset < total, total };
    } else {
      addToast('Reclassification failed', 'error');
      return { hasMore: false, total: 0 };
    }
  } catch (err) {
    addToast(`Reclassification failed: ${err.message}`, 'error');
    return { hasMore: false, total: 0 };
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
let $currentLanguageCode;
selectedVideoId.subscribe(v => $selectedVideoId = v);
currentFilter.subscribe(v => $currentFilter = v);
currentLanguage.subscribe(v => $currentLanguageCode = v);

export async function exportAnki(videoId, forceUpdateModel = false, cardType = 'basic') {
  exporting.set(true);
  exportStatus.set('⏳ Exporting...');
  try {
    const { ok, data } = await api.exportAnki(videoId, forceUpdateModel, cardType);
    if (!ok) throw new Error(data.error || 'Export failed');
    exportStatus.set(`✅ ${data.added} new, ${data.duplicates} duplicates`);
  } catch (err) {
    exportStatus.set(`❌ ${err.message}`);
  } finally {
    exporting.set(false);
  }
}

// === Word status hashmap management (M19) ===

export async function loadWordStatuses() {
  try {
    const data = await api.listVocabStatuses();
    knownWords.set(new Set(data.known || []));
    learningWords.set(new Set(data.learning || []));
    ignoredWords.set(new Set(data.ignored || []));
  } catch (err) {
    console.error('Failed to load word statuses:', err);
  }
}

export async function markWordStatus(word, status) {
  // 1. Instant client-side update
  setWordStatus(word, status);
  // 2. Async server persist (fire-and-forget)
  try {
    await updateVocabWord(word, status);
  } catch (err) {
    addToast(`Failed to save: ${err.message}`, 'error');
  }
}
