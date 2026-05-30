/** API helpers for LangMine REST endpoints. */

const BASE = '/api';

async function get(path) {
  const res = await fetch(BASE + path);
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
  return res.json();
}

async function post(path, body) {
  const res = await fetch(BASE + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return { ok: res.ok, status: res.status, data: await res.json() };
}

async function patch(path, body) {
  const res = await fetch(BASE + path, {
    method: 'PATCH',
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.error || `${res.status}`);
  }
  return res.json();
}

async function put(path, body) {
  const res = await fetch(BASE + path, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.error || `${res.status}`);
  }
  return res.json();
}

export const api = {
  listVideos: () => get('/videos'),
  mineVideo: (url, file = null) => {
    if (file) {
      // Multipart form data with transcript file
      const formData = new FormData();
      formData.append('url', url);
      formData.append('file', file);
      return fetch(BASE + '/videos/mine', { method: 'POST', body: formData })
        .then(async res => ({ ok: res.ok, status: res.status, data: await res.json() }));
    }
    return post('/videos/mine', { url });
  },
  getSentences: (videoId, status) =>
    get(`/videos/${videoId}/sentences${status && status !== 'all' ? `?status=${status}` : ''}`),
  updateSentence: (id, status) => patch(`/sentences/${id}`, { status }),
  updateSentenceFields: (id, fields) => patch(`/sentences/${id}`, fields),
  markWordKnown: (id) => patch(`/sentences/${id}/iknowthis`),
  getStats: () => get('/stats'),
  getConfig: () => get('/config'),
  updateConfig: (config) => put('/config', config),
  exportAnki: (videoId, forceUpdateModel, cardType = 'basic') =>
    post('/export/anki', {
      ...(videoId ? { video_id: videoId } : { all_kept: true }),
      force_update_model: forceUpdateModel || false,
      card_type: cardType,
    }),
};

// Vocab API calls
export async function fetchVocab(page = 1, status = null, search = null, sort = 'frequency') {
  const params = new URLSearchParams({ page, per_page: 200, sort });
  if (status) params.set('status', status);
  if (search) params.set('search', search);
  const res = await fetch(`/api/vocab?${params}`);
  return res.json();
}

export async function fetchVocabWord(word) {
  const res = await fetch(`/api/vocab/${encodeURIComponent(word)}`);
  return res.json();
}

export async function updateVocabWord(word, status) {
  const res = await fetch(`/api/vocab/${encodeURIComponent(word)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
  });
  return res.json();
}

// Image search API (M12)
export async function searchImages(query, count = 5) {
  const res = await fetch(`/api/images/search?q=${encodeURIComponent(query)}&count=${count}`);
  return res.json();
}

export async function setClozeImage(sentenceId, imageUrl) {
  const res = await fetch(`/api/sentences/${sentenceId}/cloze-image`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ image_url: imageUrl }),
  });
  return res.json();
}

// Difficulty preview API (M13)
export async function previewVideo(url) {
  const res = await fetch('/api/videos/preview', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  });
  return { ok: res.ok, status: res.status, data: await res.json() };
}
