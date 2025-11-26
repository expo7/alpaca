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
    const err = new Error(data.detail || data.error || data.message || data.raw || "Request failed");
    err.payload = data;
    throw err;
  }
  return data;
}

export async function simulateOrderFill(orderId, token) {
  return apiFetch(`/api/paper/orders/${orderId}/simulate_fill/`, token, {
    method: "POST",
  });
}
