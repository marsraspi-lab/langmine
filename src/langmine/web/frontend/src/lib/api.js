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
  deleteVideo: (id) => fetch(BASE + `/videos/${id}`, { method: 'DELETE' })
    .then(async res => ({ ok: res.ok, status: res.status, data: await res.json() })),
  /** Stream mine progress via SSE. Returns an async generator yielding
   *  {status: "message"} for progress, then the final result object. */
  mineVideoStream: async function* (url, file = null) {
    let body;
    if (file) {
      const formData = new FormData();
      formData.append('url', url);
      formData.append('file', file);
      body = formData;
    } else {
      body = JSON.stringify({ url });
    }
    const headers = { 'Accept': 'text/event-stream' };
    if (!file) headers['Content-Type'] = 'application/json';
    const res = await fetch(BASE + '/videos/mine', { method: 'POST', headers, body });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: `${res.status}` }));
      throw new Error(err.error || `Mine failed (${res.status})`);
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          yield JSON.parse(line.slice(6));
        }
      }
    }
  },
  getSentences: (videoId, status) =>
    get(`/videos/${videoId}/sentences${status && status !== 'all' ? `?status=${status}` : ''}`),
  updateSentence: (id, status) => patch(`/sentences/${id}`, { status }),
  updateSentenceFields: (id, fields) => patch(`/sentences/${id}`, fields),
  markWordKnown: (id) => patch(`/sentences/${id}/iknowthis`),
  getStats: () => get('/stats'),
  getConfig: () => get('/config'),
  updateConfig: (config) => put('/config', config),
  listLanguages: () => get('/languages'),
  listVocabStatuses: () => get('/vocab/statuses'),
  exportAnki: (videoId, forceUpdateModel, cardType = 'basic') =>
    post('/export/anki', {
      ...(videoId ? { video_id: videoId } : { all_kept: true }),
      force_update_model: forceUpdateModel || false,
      card_type: cardType,
    }),
  reclassifySentences: (videoId, offset = 0, limit = 50) =>
    post(`/videos/${videoId}/reclassify?offset=${offset}&limit=${limit}`),
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

export async function dismissProperName(word) {
  const res = await fetch(`/api/vocab/${encodeURIComponent(word)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ proper_name: false }),
  });
  if (!res.ok) {
    const data = await res.json();
    throw new Error(data.error || 'Failed to dismiss proper name');
  }
  return res.json();
}

export async function markProperName(word) {
  const res = await fetch(`/api/vocab/${encodeURIComponent(word)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ proper_name: true }),
  });
  if (!res.ok) {
    const data = await res.json();
    throw new Error(data.error || 'Failed to mark as proper name');
  }
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

// M24: Sentence joining
export async function mergeWithPrevious(sentenceId) {
  const res = await fetch(`/api/sentences/${sentenceId}/merge-with-previous`, {
    method: 'POST',
  });
  if (!res.ok) {
    const data = await res.json();
    throw new Error(data.error || 'Merge failed');
  }
  return res.json();
}
