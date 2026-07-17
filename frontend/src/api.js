// API 客户端：封装对 FastAPI 后端的请求
const BASE = '/api'

async function request(path, options = {}) {
  const resp = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`
    try {
      const data = await resp.json()
      detail = data.detail || detail
    } catch { /* ignore */ }
    throw new Error(detail)
  }
  return resp.json()
}

export const api = {
  health: () => request('/health'),

  listFiles: () => request('/files/list'),

  uploadFile: (file) => {
    const form = new FormData()
    form.append('file', file)
    return fetch(`${BASE}/files/upload`, { method: 'POST', body: form })
      .then(async (r) => {
        if (!r.ok) throw new Error((await r.json()).detail || '上传失败')
        return r.json()
      })
  },

  listInterfaces: (withTraffic = true) =>
    request(`/capture/interfaces?with_traffic=${withTraffic}`),

  getTraffic: () => request('/capture/traffic'),

  startCapture: (payload) =>
    request('/capture/start', { method: 'POST', body: JSON.stringify(payload) }),

  captureStatus: (taskId) => request(`/capture/status/${taskId}`),

  listPackets: ({ file, filter = '', offset = 0, limit = 100 }) =>
    request(
      `/packets/list?file=${encodeURIComponent(file)}&filter=${encodeURIComponent(filter)}&offset=${offset}&limit=${limit}`,
    ),

  countPackets: ({ file, filter = '' }) =>
    request(
      `/packets/count?file=${encodeURIComponent(file)}&filter=${encodeURIComponent(filter)}`,
    ),

  packetDetail: ({ file, number }) =>
    request(`/packets/detail?file=${encodeURIComponent(file)}&number=${number}`),

  packetStats: ({ file, type = 'protocol_hierarchy' }) =>
    request(`/packets/stats?file=${encodeURIComponent(file)}&type=${type}`),

  protocolDistribution: ({ file, filter = '' }) =>
    request(`/packets/distribution?file=${encodeURIComponent(file)}&filter=${encodeURIComponent(filter)}`),

  chat: (payload) => request('/chat/message', { method: 'POST', body: JSON.stringify(payload) }),

  summarize: (packets) =>
    request('/chat/summarize', { method: 'POST', body: JSON.stringify({ packets }) }),

  exportReport: (payload) =>
    fetch(`${BASE}/chat/report`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }).then((r) => r.text()),
}
