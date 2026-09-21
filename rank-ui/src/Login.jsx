// src/Login.jsx
import { useState } from "react";
import { useAuth } from "./AuthProvider.jsx";
import { APP_NAME, APP_TAGLINE } from "./brand";

const BASE = "";

export default function Login() {
  const { login } = useAuth();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");
  const [email, setEmail] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState("login");

  const isSignup = mode === "signup";

  function parseError(payload, fallback) {
    if (!payload || typeof payload !== "object") return fallback;
    if (typeof payload.detail === "string") return payload.detail;
    for (const key of Object.keys(payload)) {
      const val = payload[key];
      if (Array.isArray(val) && val.length) return val.join(" ");
      if (typeof val === "string") return val;
    }
    return fallback;
  }

  function switchMode(next) {
    setMode(next);
    setErr("");
  }

  async function onSubmit(e) {
    e.preventDefault();
    setErr("");
    setLoading(true);

    try {
      if (isSignup) {
        const res = await fetch(`${BASE}/api/register/`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            username,
            email,
            password,
            password_confirm: password2,
          }),
        });
        const json = await res.json().catch(() => ({}));
        if (!res.ok || !json.access) {
          throw new Error(parseError(json, "Sign up failed"));
        }
        login({ access: json.access, username: json.username || username });
        return;
      }

      const res = await fetch(`${BASE}/api/token/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });

      const json = await res.json().catch(() => ({}));
      if (!res.ok || !json.access) {
        throw new Error(parseError(json, "Login failed"));
      }

      login({ access: json.access, username });
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-950 p-5 shadow-xl shadow-indigo-950/20 sm:p-6">
      <div className="mb-5 border-b border-slate-800 pb-4">
        <span className="block text-[0.78rem] font-black tracking-[0.14em] text-white">
          {APP_NAME.toUpperCase()}
        </span>
        <span className="mt-1 block text-xs text-slate-500">{APP_TAGLINE}</span>
      </div>

      <h1 className="text-lg font-semibold">
        {isSignup ? "Create account" : "Sign in"}
      </h1>
      <p className="mt-1 text-sm text-slate-400">
        {isSignup ? "Start saving the research that matters to you." : "Continue with your Quantelle account."}
      </p>

      <div className="mt-4 flex gap-2 text-xs">
        <button
          type="button"
          onClick={() => switchMode("login")}
          className={`rounded-md border px-3 py-1.5 transition ${!isSignup
            ? "border-indigo-500 bg-indigo-600 text-white"
            : "border-slate-700 text-slate-400 hover:bg-slate-900 hover:text-slate-200"
            }`}
        >
          Sign in
        </button>
        <button
          type="button"
          onClick={() => switchMode("signup")}
          className={`rounded-md border px-3 py-1.5 transition ${isSignup
            ? "border-indigo-500 bg-indigo-600 text-white"
            : "border-slate-700 text-slate-400 hover:bg-slate-900 hover:text-slate-200"
            }`}
        >
          Create account
        </button>
      </div>

      {err && (
        <div className="mt-3 rounded-xl border border-rose-900 bg-rose-950/30 p-2 text-xs text-rose-300">
          {err}
        </div>
      )}

      <form onSubmit={onSubmit} className="mt-5 space-y-3">
            <div className="grid gap-3">
              <div>
                <label className="block text-xs text-slate-400 mb-1">
                  Username
                </label>
                <input
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  autoComplete={isSignup ? "new-username" : "username"}
                  required
                />
              </div>

              {isSignup && (
                <div>
                  <label className="block text-xs text-slate-400 mb-1">
                    Email (optional)
                  </label>
                  <input
                    type="email"
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    autoComplete="email"
                  />
                </div>
              )}

              <div>
                <label className="block text-xs text-slate-400 mb-1">
                  Password
                </label>
                <input
                  type="password"
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete={isSignup ? "new-password" : "current-password"}
                  required
                />
              </div>

              {isSignup && (
                <div>
                  <label className="block text-xs text-slate-400 mb-1">
                    Confirm password
                  </label>
                  <input
                    type="password"
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm"
                    value={password2}
                    onChange={(e) => setPassword2(e.target.value)}
                    autoComplete="new-password"
                    required
                  />
                </div>
              )}
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2 mt-1 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-60 text-sm font-medium"
            >
              {loading
                ? isSignup
                  ? "Creating..."
                  : "Signing in..."
                : isSignup
                  ? "Create account"
                  : "Sign in"}
            </button>
      </form>

      <ul className="mt-5 list-disc space-y-1 pl-4 text-xs text-slate-400">
        <li>See today&apos;s market outlook.</li>
        <li>Get a clear daily recommendation.</li>
        <li>Focus on top-ranked opportunities.</li>
        <li>Track your saved watchlist daily.</li>
      </ul>
    </section>
  );
}
