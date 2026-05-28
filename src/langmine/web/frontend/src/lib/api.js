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
  mineVideo: (url) => post('/videos/mine', { url }),
  getSentences: (videoId, status) =>
    get(`/videos/${videoId}/sentences${status && status !== 'all' ? `?status=${status}` : ''}`),
  updateSentence: (id, status) => patch(`/sentences/${id}`, { status }),
  updateSentenceFields: (id, fields) => patch(`/sentences/${id}`, fields),
  markWordKnown: (id) => patch(`/sentences/${id}/iknowthis`),
  getStats: () => get('/stats'),
  getConfig: () => get('/config'),
  updateConfig: (config) => put('/config', config),
  exportAnki: (videoId, forceUpdateModel) =>
    post('/export/anki', {
      ...(videoId ? { video_id: videoId } : { all_kept: true }),
      force_update_model: forceUpdateModel || false,
    }),
};
