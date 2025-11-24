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

export async function validateStrategy(strategy, token) {
  return apiFetch("/api/strategies/validate/", token, {
    method: "POST",
    body: JSON.stringify(strategy),
  });
}

export async function runBacktest(strategy, bot, startDate, endDate, token) {
  return apiFetch("/api/backtests/run/", token, {
    method: "POST",
    body: JSON.stringify({
      strategy,
      bot,
      start_date: startDate,
      end_date: endDate,
    }),
  });
}

export async function createBatchBacktest(payload, token) {
  return apiFetch("/api/backtests/batch/", token, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getBatchBacktest(batchId, token) {
  return apiFetch(`/api/backtests/batch/${batchId}/`, token, {
    method: "GET",
  });
}
