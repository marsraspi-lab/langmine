// stores.svelte.js — Svelte 5 runes (module-level shared state)
//
// All state lives inside a single $state({}) object so property mutations
// (app.selectedVideoId = x) are reactive while the export binding itself
// is never reassigned — compatible with Rolldown/Vite bundlers.

import { api } from './api.js';
import { updateVocabWord } from './api.js';

const FRIENDLY_ERRORS = {
  transcript: 'Could not download transcript. The video may not have subtitles.',
  classification: 'Could not classify sentences. Try again or check language settings.',
  enrichment: 'Could not generate translations. The language processor may be unavailable.',
  unknown: null,
};

// --- Single reactive state object ---

export const app = $state({
  videos: [],
  sentences: [],
  selectedVideoId: null,
  currentFilter: 'all',
  mineStatus: '',
  mining: false,
  exportStatus: '',
  exporting: false,
  toasts: [],
  config: {},
  theme: (typeof localStorage !== 'undefined' && localStorage.getItem('langmine-theme')) || 'dark',
  currentView: 'curation',
  vocabSearchQuery: '',
  languages: [],
  currentLanguage: 'zh',
  knownWords: new Set(),
  learningWords: new Set(),
  ignoredWords: new Set(),
  readingMode: false,
  reclassifyOffset: 0,
});

// --- Derived values ---
// Using $state + $effect instead of $derived so the getter function
// returns a $state value that Svelte's reactivity tracker can follow.
// (Plain $derived wrapped in a getter breaks the tracking chain.)

let _curatedSentences = $state([]);
let _selectedVideo = $state(null);

$effect(() => {
  _curatedSentences = app.sentences.map(s => {
    const tokens = (s.text_segmented || '').split(' / ').filter(Boolean);
    const unknown = tokens.filter(w =>
      !app.knownWords.has(w) && !app.ignoredWords.has(w)
    );
    const count = unknown.length;
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
        app.knownWords.has(w) ? 'known'
          : app.ignoredWords.has(w) ? 'ignored'
          : app.learningWords.has(w) ? 'learning'
          : 'unknown'
      ])),
    };
  });
});

$effect(() => {
  _selectedVideo = app.videos.find(v => v.id === app.selectedVideoId) || null;
});

export function curatedSentences() { return _curatedSentences; }
export function selectedVideo() { return _selectedVideo; }

// --- Word status helpers ---

export function setWordStatus(word, newStatus) {
  const allStores = { known: app.knownWords, learning: app.learningWords, ignored: app.ignoredWords };
  for (const [status, setObj] of Object.entries(allStores)) {
    if (status === newStatus) {
      setObj.add(word);
    } else {
      setObj.delete(word);
    }
  }
}

// --- Toast functions ---

let toastId = 0;

export function addToast(message, type = 'info', duration = 4000) {
  const id = ++toastId;
  app.toasts.push({ id, message, type });
  if (duration > 0) {
    setTimeout(() => removeToast(id), duration);
  }
  return id;
}

export function removeToast(id) {
  const idx = app.toasts.findIndex(t => t.id === id);
  if (idx !== -1) app.toasts.splice(idx, 1);
}

// --- Async functions ---

export async function loadVideos() {
  const data = await api.listVideos();
  app.videos.splice(0, app.videos.length, ...data.videos);
}

export async function deleteVideo(id) {
  const { ok, data } = await api.deleteVideo(id);
  if (!ok) {
    addToast(data?.error || 'Failed to delete video', 'error');
    return false;
  }
  addToast('Video deleted', 'success', 2000);
  if (app.selectedVideoId === id) {
    app.selectedVideoId = null;
    app.sentences.length = 0;
  }
  await loadVideos();
  return true;
}

export async function selectVideo(id) {
  app.selectedVideoId = id;
  app.currentFilter = 'all';
  app.currentView = 'curation';
  await loadSentences(id, 'all');
}

export async function loadSentences(videoId, filter) {
  const data = await api.getSentences(videoId, filter);
  app.sentences.splice(0, app.sentences.length, ...data.sentences);
}

export async function mineVideo(url, file = null, language = '') {
  app.mining = true;
  app.mineStatus = '⏳ Mining...';
  try {
    let data;
    for await (const event of api.mineVideoStream(url, file, language)) {
      if (event.error) {
        const err = event.error;
        const msg = err?.message ?? (typeof err === 'string' ? err : JSON.stringify(err));
        const stage = err?.stage;
        const friendly = FRIENDLY_ERRORS[stage];
        if (friendly) {
          throw new Error(msg && msg !== friendly ? msg : friendly);
        }
        throw new Error(msg.length > 200 ? msg.slice(0, 197) + '…' : msg);
      } else if (event.status) {
        app.mineStatus = `⏳ ${event.status}`;
      } else {
        data = event;
      }
    }
    if (!data) {
      app.mineStatus = '❌ No result';
      return null;
    }
    app.mineStatus = `✅ ${data.total_sentences} sentences, ${data.i1_count} i+1`;
    await loadVideos();
    if (data.video_id) {
      await selectVideo(data.video_id);
    }
    return data;
  } catch (err) {
    console.error('[mine]', err);
    app.mineStatus = `❌ ${err.message}`;
    return null;
  } finally {
    app.mining = false;
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
    Object.assign(app.config, data);
    if (data.source_language) {
      app.currentLanguage = data.source_language;
    }
  } catch (err) {
    console.error('Failed to load config:', err);
  }
}

export async function loadLanguages() {
  try {
    const data = await api.listLanguages();
    app.languages.splice(0, app.languages.length, ...data.languages);
  } catch (err) {
    console.error('Failed to load languages:', err);
  }
}

export async function selectLanguage(code) {
  if (code === app.currentLanguage) return;
  try {
    await api.updateConfig({ source_language: code });
    app.currentLanguage = code;
    app.config.source_language = code;
    addToast(`Switched to ${code}`, 'info', 2000);
    await loadVideos();
    if (app.selectedVideoId) {
      await loadSentences(app.selectedVideoId, app.currentFilter);
    }
  } catch (err) {
    addToast(`Failed to switch language: ${err.message}`, 'error');
  }
}

export async function reclassifyAndLoad(videoId, offset = 0, limit = 50) {
  try {
    const res = await api.reclassifySentences(videoId, offset, limit);
    if (res.ok) {
      const { sentences: newSentences, total } = res.data;
      if (offset === 0) {
        app.sentences.splice(0, app.sentences.length, ...newSentences);
      } else {
        app.sentences.push(...newSentences);
      }
      app.reclassifyOffset = offset + newSentences.length;
      return { hasMore: app.reclassifyOffset < total, total };
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
    Object.assign(app.config, updates);
    addToast('Settings saved ✓', 'success', 2000);
  } catch (err) {
    addToast(`Failed to save: ${err.message}`, 'error');
  }
}

export function toggleTheme() {
  app.theme = app.theme === 'dark' ? 'light' : 'dark';
}

async function refreshAfterAction() {
  await loadVideos();
  const vidId = app.selectedVideoId;
  const filter = app.currentFilter;
  if (vidId) {
    await loadSentences(vidId, filter);
  }
}

export async function exportAnki(videoId, forceUpdateModel = false, cardType = 'basic') {
  app.exporting = true;
  app.exportStatus = '⏳ Exporting...';
  try {
    const { ok, data } = await api.exportAnki(videoId, forceUpdateModel, cardType);
    if (!ok) throw new Error(data.error || 'Export failed');
    app.exportStatus = `✅ ${data.added} new, ${data.duplicates} duplicates`;
  } catch (err) {
    app.exportStatus = `❌ ${err.message}`;
  } finally {
    app.exporting = false;
  }
}

export async function loadWordStatuses() {
  try {
    const data = await api.listVocabStatuses();
    app.knownWords.clear();
    for (const w of data.known || []) app.knownWords.add(w);
    app.learningWords.clear();
    for (const w of data.learning || []) app.learningWords.add(w);
    app.ignoredWords.clear();
    for (const w of data.ignored || []) app.ignoredWords.add(w);
  } catch (err) {
    console.error('Failed to load word statuses:', err);
  }
}

export async function markWordStatus(word, status) {
  setWordStatus(word, status);
  try {
    await updateVocabWord(word, status);
  } catch (err) {
    addToast(`Failed to save: ${err.message}`, 'error');
  }
}
