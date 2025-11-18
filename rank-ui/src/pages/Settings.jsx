// ==============================
// File: src/pages/Settings.jsx
// Controls:
//  - Local ranking defaults (tickers, weights)
//  - Per-user daily scan email toggle + thresholds
// ==============================

import { useEffect, useState } from "react";
import { useAuth } from "../AuthProvider.jsx";

const BASE = "http://127.0.0.1:8000";

// small helper for calling the API with JWT
async function apiFetch(path, token, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${BASE}${path}`, { ...options, headers });
  const text = await res.text();
  let data = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { raw: text };
  }
  if (!res.ok) {
    const msg = data.detail || data.error || data.raw || `HTTP ${res.status}`;
    throw new Error(msg);
  }
  return data;
}

export default function Settings({
  tickers,
  techWeight,
  fundWeight,
  ta,
  setTickers,
  setTechWeight,
  setFundWeight,
  setTa,
}) {
  const { token } = useAuth();

  // --- local copy for ranking defaults (just UX niceness) ---
  const [localTickers, setLocalTickers] = useState(tickers);
  const [localTech, setLocalTech] = useState(techWeight);
  const [localFund, setLocalFund] = useState(fundWeight);
  const [localTa, setLocalTa] = useState(ta);

  useEffect(() => setLocalTickers(tickers), [tickers]);
  useEffect(() => setLocalTech(techWeight), [techWeight]);
  useEffect(() => setLocalFund(fundWeight), [fundWeight]);
  useEffect(() => setLocalTa(ta), [ta]);

  function saveRankingDefaults() {
    setTickers(localTickers);
    setTechWeight(localTech);
    setFundWeight(localFund);
    setTa(localTa);
  }

  // --- per-user daily scan prefs (backend) ---
  const [loadingPrefs, setLoadingPrefs] = useState(true);
  const [prefErr, setPrefErr] = useState("");
  const [scanEnabled, setScanEnabled] = useState(false);
  const [scanMinScore, setScanMinScore] = useState(15);
  const [scanMaxIdeas, setScanMaxIdeas] = useState(10);
  const [savingPrefs, setSavingPrefs] = useState(false);
  const [savedAt, setSavedAt] = useState(null);

  // load prefs on mount
  useEffect(() => {
    if (!token) return;
    let cancelled = false;

    async function loadPrefs() {
      setLoadingPrefs(true);
      setPrefErr("");
      try {
        const data = await apiFetch("/api/user-prefs/", token);
        if (cancelled) return;
        setScanEnabled(!!data.daily_scan_enabled);
        if (typeof data.daily_scan_min_score === "number") {
          setScanMinScore(data.daily_scan_min_score);
        }
        if (typeof data.daily_scan_max_ideas === "number") {
          setScanMaxIdeas(data.daily_scan_max_ideas);
        }
      } catch (e) {
        if (!cancelled) setPrefErr(e.message || String(e));
      } finally {
        if (!cancelled) setLoadingPrefs(false);
      }
    }

    loadPrefs();
    return () => {
      cancelled = true;
    };
  }, [token]);

  async function savePrefs() {
    if (!token) return;
    setSavingPrefs(true);
    setPrefErr("");
    try {
      const payload = {
        daily_scan_enabled: scanEnabled,
        daily_scan_min_score: Number(scanMinScore),
        daily_scan_max_ideas: Number(scanMaxIdeas),
      };
      await apiFetch("/api/user-prefs/", token, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      setSavedAt(new Date());
    } catch (e) {
      setPrefErr(e.message || String(e));
    } finally {
      setSavingPrefs(false);
    }
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-4 flex items-center justify-between">
        <div>
          <div className="text-lg font-semibold">Settings</div>
          <div className="text-sm text-slate-400">
            Control your default basket, weights, and email preferences.
          </div>
        </div>
      </div>

      {/* Layout: two responsive columns */}
      <div className="grid lg:grid-cols-2 gap-4">
        {/* LEFT: Ranking defaults (local app state) */}
        <div className="space-y-4">
          <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-4">
            <div className="text-sm font-semibold mb-2">
              Ranking defaults
            </div>
            <p className="text-xs text-slate-400 mb-3">
              These defaults are stored locally in your browser and applied on
              the dashboard when you refresh.
            </p>

            <div className="space-y-3">
              <div>
                <label className="block text-sm mb-1">
                  Default tickers (comma-separated)
                </label>
                <input
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm"
                  value={localTickers}
                  onChange={(e) => setLocalTickers(e.target.value)}
                  placeholder="AAPL, MSFT, NVDA, TSLA, AMD"
                />
              </div>

              <div className="grid grid-cols-2 gap-3 text-sm">
                <NumberInput
                  label="Tech weight"
                  value={localTech}
                  setValue={setLocalTech}
                  step={0.05}
                />
                <NumberInput
                  label="Fund weight"
                  value={localFund}
                  setValue={setLocalFund}
                  step={0.05}
                />
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-sm">
                {["trend", "momentum", "volume", "volatility", "meanreversion"].map(
                  (k) => (
                    <NumberInput
                      key={k}
                      label={`TA ${k}`}
                      value={localTa[k]}
                      setValue={(v) =>
                        setLocalTa((prev) => ({ ...prev, [k]: v }))
                      }
                      step={0.05}
                    />
                  )
                )}
              </div>
            </div>

            <div className="flex justify-end mt-4">
              <button
                type="button"
                onClick={saveRankingDefaults}
                className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-sm"
              >
                Save ranking defaults
              </button>
            </div>
          </div>
        </div>

        {/* RIGHT: Daily scan email prefs (server-backed) */}
        <div className="space-y-4">
          <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-4">
            <div className="text-sm font-semibold mb-2">
              Daily scan email
            </div>
            <p className="text-xs text-slate-400 mb-3">
              Control whether you receive the once-per-day scan idea email
              (driven by your cron job).
            </p>

            {!token && (
              <div className="text-xs text-rose-300">
                You must be logged in to edit email preferences.
              </div>
            )}

            {token && (
              <>
                {loadingPrefs ? (
                  <div className="text-xs text-slate-400">
                    Loading preferences…
                  </div>
                ) : (
                  <>
                    <label className="inline-flex items-center gap-2 text-sm mb-3">
                      <input
                        type="checkbox"
                        checked={scanEnabled}
                        onChange={() => setScanEnabled((v) => !v)}
                      />
                      Enable daily scan email
                    </label>

                    <div className="grid grid-cols-2 gap-3 text-sm mt-1">
                      <div>
                        <label className="block text-xs text-slate-400 mb-1">
                          Minimum final score
                        </label>
                        <input
                          type="number"
                          value={scanMinScore}
                          onChange={(e) =>
                            setScanMinScore(Number(e.target.value))
                          }
                          className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-slate-400 mb-1">
                          Max ideas per email
                        </label>
                        <input
                          type="number"
                          min={1}
                          value={scanMaxIdeas}
                          onChange={(e) =>
                            setScanMaxIdeas(Number(e.target.value))
                          }
                          className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm"
                        />
                      </div>
                    </div>

                    {prefErr && (
                      <div className="mt-3 text-xs text-rose-300">
                        {prefErr}
                      </div>
                    )}
                    {savedAt && !prefErr && (
                      <div className="mt-2 text-[11px] text-emerald-400">
                        Saved at {savedAt.toLocaleTimeString()}
                      </div>
                    )}

                    <div className="flex justify-end mt-4">
                      <button
                        type="button"
                        onClick={savePrefs}
                        disabled={savingPrefs}
                        className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-60 text-sm"
                      >
                        {savingPrefs ? "Saving…" : "Save email settings"}
                      </button>
                    </div>
                  </>
                )}
              </>
            )}
          </div>

          <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-4 text-xs text-slate-400">
            <div className="font-semibold mb-1">How this works</div>
            <ul className="list-disc pl-4 space-y-1">
              <li>
                Your cron job runs the daily scan management command.
              </li>
              <li>
                Only users with <code>daily_scan_enabled</code> turned on will
                receive that email.
              </li>
              <li>
                The score threshold and max ideas fields give you basic control
                over idea quality and email length.
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}

function NumberInput({ label, value, setValue, step = 0.05 }) {
  return (
    <div>
      <label className="block text-sm mb-1">{label}</label>
      <input
        type="number"
        step={step}
        value={value}
        onChange={(e) => setValue(Number(e.target.value))}
        className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
      />
    </div>
  );
}
