// ==============================
// File: src/pages/Alerts.jsx
// Simple CRUD UI for alerts + history + inline "Test now" status
// ==============================

import { useEffect, useState } from "react";
import { useAuth } from "../AuthProvider.jsx";
import AlertHistoryPanel from "../components/AlertHistoryPanel";

const BASE = "http://127.0.0.1:8000";

// small helper for calling the API with JWT
async function apiFetch(path, token, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${BASE}${path}`, { ...options, headers });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg =
      data.detail ||
      data.error ||
      JSON.stringify(data) ||
      `HTTP ${res.status}`;
    throw new Error(msg);
  }
  return data;
}

export default function Alerts() {
  const { token } = useAuth();

  const [alerts, setAlerts] = useState([]);
  const [watchlists, setWatchlists] = useState([]);
  const [err, setErr] = useState("");

  // form state
  const [alertType, setAlertType] = useState("symbol"); // "symbol" | "watchlist"
  const [symbol, setSymbol] = useState("");
  const [watchlistId, setWatchlistId] = useState("");
  const [minFinal, setMinFinal] = useState(15);
  const [minTech, setMinTech] = useState("");
  const [minFund, setMinFund] = useState("");
  const [triggerOnce, setTriggerOnce] = useState(true);

  // [TEST-UI-STATE] per-alert test info: { [id]: { loading, error, last: {...} } }
  const [testInfo, setTestInfo] = useState({});

  // ------- "Test alert now" -------

  async function testAlert(alertObj) {
    const id = alertObj.id;
    try {
      setErr("");
      setTestInfo((prev) => ({
        ...prev,
        [id]: {
          ...(prev[id] || {}),
          loading: true,
          error: "",
        },
      }));

      const data = await apiFetch(`/api/alerts/${id}/test/`, token, {
        method: "POST",
      });

      const results = Array.isArray(data.results) ? data.results : [];
      const anyTriggered = results.some((r) => r.triggered);

      setTestInfo((prev) => ({
        ...prev,
        [id]: {
          loading: false,
          error: "",
          last: {
            timestamp: data.timestamp,
            results,
            anyTriggered,
          },
        },
      }));
    } catch (e) {
      const message = e.message || String(e);
      setErr(message);
      setTestInfo((prev) => ({
        ...prev,
        [id]: {
          ...(prev[id] || {}),
          loading: false,
          error: message,
        },
      }));
    }
  }

  // ------- load data -------

  async function loadAlerts() {
    try {
      setErr("");
      const data = await apiFetch("/api/alerts/", token);
      setAlerts(Array.isArray(data) ? data : []);
    } catch (e) {
      setErr(e.message || String(e));
    }
  }

  async function loadWatchlists() {
    try {
      const data = await apiFetch("/api/watchlists/", token);
      const list = Array.isArray(data) ? data : [];
      setWatchlists(list);
      if (list.length && !watchlistId) {
        setWatchlistId(String(list[0].id));
      }
    } catch {
      // non-fatal
    }
  }

  useEffect(() => {
    if (!token) return;
    loadAlerts();
    loadWatchlists();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  // ------- actions -------

  async function createAlert() {
    try {
      setErr("");
      const body = {
        alert_type: alertType,
        symbol:
          alertType === "symbol" ? symbol.trim().toUpperCase() : null,
        watchlist:
          alertType === "watchlist" && watchlistId
            ? Number(watchlistId)
            : null,
        min_final_score: Number(minFinal),
        min_tech_score: minTech === "" ? null : Number(minTech),
        min_fund_score: minFund === "" ? null : Number(minFund),
        trigger_once: triggerOnce,
        active: true,
      };

      await apiFetch("/api/alerts/", token, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      setSymbol("");
      loadAlerts();
    } catch (e) {
      setErr(e.message || String(e));
    }
  }

  async function deleteAlert(id) {
    try {
      setErr("");
      await apiFetch(`/api/alerts/${id}/`, token, {
        method: "DELETE",
      });
      setAlerts((prev) => prev.filter((a) => a.id !== id));
    } catch (e) {
      setErr(e.message || String(e));
    }
  }

  async function toggleActive(alert) {
    try {
      setErr("");
      await apiFetch(`/api/alerts/${alert.id}/`, token, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ active: !alert.active }),
      });
      loadAlerts();
    } catch (e) {
      setErr(e.message || String(e));
    }
  }

  // ------- render -------

  if (!token) {
    return (
      <div className="text-sm text-rose-300">
        No token found – you must be logged in.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Create alert */}
      <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-4">
        <div className="text-lg font-semibold">Alerts</div>
        <p className="text-sm text-slate-400 mt-1">
          Create alerts that fire when scores cross your thresholds.
          The{" "}
          <code className="bg-slate-800 px-1 rounded text-xs">
            check_alerts
          </code>{" "}
          management command should be run periodically (e.g. via cron).
        </p>

        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {/* left: target */}
          <div className="space-y-3">
            <div className="flex gap-3 text-sm">
              <label className="inline-flex items-center gap-2">
                <input
                  type="radio"
                  name="atype"
                  value="symbol"
                  checked={alertType === "symbol"}
                  onChange={() => setAlertType("symbol")}
                />
                Symbol
              </label>
              <label className="inline-flex items-center gap-2">
                <input
                  type="radio"
                  name="atype"
                  value="watchlist"
                  checked={alertType === "watchlist"}
                  onChange={() => setAlertType("watchlist")}
                />
                Watchlist
              </label>
            </div>

            {alertType === "symbol" ? (
              <input
                value={symbol}
                onChange={(e) => setSymbol(e.target.value)}
                placeholder="e.g., AAPL"
                className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm"
              />
            ) : (
              <select
                value={watchlistId}
                onChange={(e) => setWatchlistId(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm"
              >
                {watchlists.map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.name}
                  </option>
                ))}
                {!watchlists.length && (
                  <option value="">No watchlists</option>
                )}
              </select>
            )}
          </div>

          {/* right: thresholds */}
          <div className="space-y-2 text-sm">
            <div className="grid grid-cols-3 gap-2">
              <div>
                <label className="block text-xs text-slate-400">
                  Min final
                </label>
                <input
                  type="number"
                  value={minFinal}
                  onChange={(e) => setMinFinal(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl p-1.5 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-400">
                  Min tech
                </label>
                <input
                  type="number"
                  value={minTech}
                  onChange={(e) => setMinTech(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl p-1.5 text-sm"
                  placeholder="optional"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-400">
                  Min fund
                </label>
                <input
                  type="number"
                  value={minFund}
                  onChange={(e) => setMinFund(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl p-1.5 text-sm"
                  placeholder="optional"
                />
              </div>
            </div>

            <label className="inline-flex items-center gap-2 mt-2">
              <input
                type="checkbox"
                checked={triggerOnce}
                onChange={() => setTriggerOnce((v) => !v)}
              />
              Trigger once (disable after first hit)
            </label>

            <div className="pt-2">
              <button
                onClick={createAlert}
                className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-sm"
              >
                Create alert
              </button>
            </div>
          </div>
        </div>

        {err && (
          <div className="mt-3 text-rose-300 text-xs whitespace-pre-wrap break-words">
            {err}
          </div>
        )}
      </div>

      {/* list alerts */}
      <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-4">
        <div className="text-sm font-semibold mb-2">Your alerts</div>
        <div className="space-y-2 text-sm">
          {alerts.map((a) => {
            const t = testInfo[a.id];
            const last = t?.last;
            const firstRes = last?.results?.[0];
            const finalVal =
              typeof firstRes?.final_score === "number"
                ? firstRes.final_score
                : null;
            const finalStr = finalVal !== null ? finalVal.toFixed(2) : "n/a";
            const symbolStr = firstRes?.symbol || a.symbol;

            return (
              <div
                key={a.id}
                className="flex flex-col gap-2 border border-slate-800 rounded-xl px-3 py-2"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div>
                    <div className="font-semibold">
                      {a.alert_type === "symbol" ? (
                        <span>{a.symbol}</span>
                      ) : (
                        <span>Watchlist #{a.watchlist}</span>
                      )}
                      <span className="ml-2 text-xs text-slate-400">
                        ≥ {a.min_final_score}
                      </span>
                    </div>
                    <div className="text-xs text-slate-400">
                      Tech ≥ {a.min_tech_score ?? "-"} · Fund ≥{" "}
                      {a.min_fund_score ?? "-"}
                    </div>
                    {a.last_triggered_at && (
                      <div className="text-xs text-emerald-400">
                        Last triggered:{" "}
                        {new Date(a.last_triggered_at).toLocaleString()}
                      </div>
                    )}
                  </div>

                  <div className="flex gap-2 justify-end">
                    {/* TEST ALERT NOW BUTTON */}
                    <button
                      onClick={() => testAlert(a)}
                      disabled={t?.loading}
                      className={`px-3 py-1.5 rounded-lg text-xs border ${
                        t?.loading
                          ? "border-blue-900 text-blue-400 bg-blue-950/40 cursor-wait"
                          : "border-blue-700 text-blue-300 hover:bg-blue-900"
                      }`}
                    >
                      {t?.loading ? "Testing…" : "Test"}
                    </button>

                    <button
                      onClick={() => toggleActive(a)}
                      className={`px-3 py-1.5 rounded-lg text-xs border ${
                        a.active
                          ? "border-emerald-500 text-emerald-300"
                          : "border-slate-700 text-slate-400"
                      }`}
                    >
                      {a.active ? "Active" : "Paused"}
                    </button>
                    <button
                      onClick={() => deleteAlert(a.id)}
                      className="px-3 py-1.5 rounded-lg text-xs border border-rose-900 text-rose-200 hover:bg-rose-950"
                    >
                      Delete
                    </button>
                  </div>
                </div>

                {/* [TEST-UI-ROW] inline last-test status */}
                {t?.error && (
                  <div className="text-[11px] text-rose-300">
                    Test error: {t.error}
                  </div>
                )}

                {last && (
                  <div className="text-[11px] text-slate-400 flex flex-wrap items-center gap-1">
                    <span className="text-slate-500">Last test:</span>
                    <span>
                      {new Date(last.timestamp).toLocaleString()}
                    </span>
                    <span className="mx-1">·</span>
                    {last.anyTriggered ? (
                      <span className="text-emerald-300">
                        Would trigger now for{" "}
                        <span className="font-semibold">{symbolStr}</span>{" "}
                        (Final {finalStr} ≥ {a.min_final_score})
                      </span>
                    ) : (
                      <span className="text-amber-300">
                        Below threshold for{" "}
                        <span className="font-semibold">{symbolStr}</span>{" "}
                        (Final {finalStr} &lt; {a.min_final_score})
                      </span>
                    )}
                  </div>
                )}
              </div>
            );
          })}
          {!alerts.length && (
            <div className="text-slate-500 text-xs">No alerts yet.</div>
          )}
        </div>
      </div>

      {/* === ALERT HISTORY PANEL === */}
      <AlertHistoryPanel />
    </div>
  );
}
