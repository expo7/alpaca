// src/Login.jsx
import { useState } from "react";
import { useAuth } from "./AuthProvider.jsx";
import { APP_NAME, APP_TAGLINE } from "./brand";

const BASE = "http://127.0.0.1:8000";

export default function Login() {
  const { login } = useAuth();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e) {
    e.preventDefault();
    setErr("");
    setLoading(true);

    try {
      const res = await fetch(`${BASE}/api/token/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });

      const json = await res.json().catch(() => ({}));
      if (!res.ok || !json.access) throw new Error(json?.detail || "Login failed");

      login({ access: json.access, username });
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center px-4">
      <div className="w-full max-w-lg">
        {/* Brand */}
        <div className="mb-4 text-center">
          <div className="inline-flex items-center gap-3">
            <div className="h-9 w-9 rounded-2xl bg-indigo-600 flex items-center justify-center shadow-md shadow-indigo-900/30">
              <span className="text-sm font-bold">SR</span>
            </div>
            <div className="flex flex-col text-left">
              <span className="text-sm font-semibold tracking-wide">{APP_NAME}</span>
              <span className="text-xs text-slate-400">{APP_TAGLINE}</span>
            </div>
          </div>
        </div>

        {/* Card */}
        <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-5 shadow-lg">
          <h1 className="text-lg font-semibold text-center">Sign in</h1>

          {err && (
            <div className="text-xs text-rose-300 bg-rose-950/30 border border-rose-900 rounded-xl p-2 mt-3">
              {err}
            </div>
          )}

          {/* Form */}
          <form onSubmit={onSubmit} className="space-y-3 mt-4">
            <div>
              <label className="block text-xs text-slate-400 mb-1">Username</label>
              <input
                className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                required
              />
            </div>

            <div>
              <label className="block text-xs text-slate-400 mb-1">Password</label>
              <input
                type="password"
                className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2 mt-1 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-60 text-sm font-medium"
            >
              {loading ? "Signing in..." : "Sign in"}
            </button>
          </form>

          {/* Value props — compact */}
          <ul className="mt-4 text-xs text-slate-400 space-y-1 list-disc pl-4">
            <li>Rank any basket of tickers.</li>
            <li>Technical + fundamental scoring.</li>
            <li>TradingView charting & explain panel.</li>
            <li>Email alerts when scores move.</li>
            <li>Simple Top-N backtests vs SPY.</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
