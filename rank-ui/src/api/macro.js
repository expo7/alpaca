const BASE = "http://127.0.0.1:8000";

function looksLikeHtml(text = "") {
  const normalized = String(text || "").trim().toLowerCase();
  return normalized.startsWith("<!doctype html") || normalized.startsWith("<html");
}

function buildErrorMessage(res, data, text) {
  if (looksLikeHtml(text)) {
    return `Server error (${res.status}). Please try again.`;
  }
  return (
    data.detail ||
    data.error ||
    data.message ||
    `Request failed with status ${res.status}`
  );
}

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
    data = {};
  }

  if (!res.ok) {
    const err = new Error(buildErrorMessage(res, data, text));
    err.payload = data;
    err.status = res.status;
    throw err;
  }

  if (!data || typeof data !== "object" || Array.isArray(data)) {
    throw new Error("Unexpected server response format.");
  }

  return data;
}

export async function getMacroDashboard(token, params = {}) {
  const query = new URLSearchParams();
  Object.entries(params || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, String(value));
    }
  });
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return apiFetch(`/api/macro/dashboard/${suffix}`, token, { method: "GET" });
}
