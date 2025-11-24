const BASE = "http://127.0.0.1:8000";

async function apiFetch(path, token, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (options.body && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`${BASE}${path}`, { ...options, headers });
  const text = await res.text();
  let data = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { raw: text };
  }

  if (!res.ok) {
    const err = new Error(
      data.detail || data.error || data.message || data.raw || `HTTP ${res.status}`
    );
    err.payload = data;
    throw err;
  }

  return data;
}

export async function fetchBots(token) {
  return apiFetch("/api/bots/", token, { method: "GET" });
}

export async function startBot(id, token) {
  return apiFetch(`/api/bots/${id}/start/`, token, { method: "POST" });
}

export async function pauseBot(id, token) {
  return apiFetch(`/api/bots/${id}/pause/`, token, { method: "POST" });
}

export async function stopBot(id, token) {
  return apiFetch(`/api/bots/${id}/stop/`, token, { method: "POST" });
}
