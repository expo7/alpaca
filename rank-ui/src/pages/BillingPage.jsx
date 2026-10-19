import { useEffect, useState } from "react";

function authHeaders(token) {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export default function BillingPage({ token, isAuthed }) {
  const [billing, setBilling] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!isAuthed) return;
    let cancelled = false;
    fetch("/api/billing/status/", { headers: authHeaders(token) })
      .then(async (response) => {
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || "Unable to load billing status.");
        if (!cancelled) setBilling(data);
      })
      .catch((err) => { if (!cancelled) setError(err.message); });
    return () => { cancelled = true; };
  }, [isAuthed, token]);

  async function openBilling(path) {
    setBusy(true);
    setError("");
    try {
      const response = await fetch(path, { method: "POST", headers: authHeaders(token) });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "Unable to open Stripe.");
      window.location.assign(data.url);
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  const isPro = Boolean(billing?.is_pro);

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-8 sm:px-6">
      <div className="mx-auto max-w-3xl text-center">
        <div className="text-xs font-bold uppercase tracking-[0.18em] text-indigo-300">Quantelle Pro</div>
        <h1 className="mt-3 text-4xl font-bold text-white">The actionable layer</h1>
        <p className="mx-auto mt-4 max-w-2xl text-lg leading-8 text-slate-300">
          See active stock and options setups before the outcome is known, including entry conditions, live contract context, stops, targets, evidence, and timestamped updates.
        </p>
      </div>

      <div className="mx-auto mt-8 max-w-xl rounded-3xl border border-indigo-500/50 bg-slate-900 p-6 shadow-2xl shadow-indigo-950/30 sm:p-8">
        <div className="flex items-end justify-between gap-4">
          <div><div className="text-xl font-bold text-white">Quantelle Pro</div><div className="mt-1 text-sm text-slate-400">Cancel anytime</div></div>
          <div className="text-right"><span className="text-4xl font-bold text-white">$49</span><span className="text-slate-400"> / month</span></div>
        </div>
        <ul className="mt-6 space-y-3 text-slate-200">
          {[
            "Active trade setups and entry triggers",
            "Option contract, bid/ask, liquidity, stops, and targets",
            "Timestamped changes and paper-trading outcomes",
            "The research evidence behind every setup",
            "A permanent public record after each setup ends",
          ].map((item) => <li key={item} className="flex gap-3"><span className="text-emerald-400">✓</span><span>{item}</span></li>)}
        </ul>

        {error && <div className="mt-5 rounded-xl border border-rose-800 bg-rose-950/40 p-3 text-sm text-rose-200">{error}</div>}

        {!isAuthed ? (
          <a href="/" className="mt-6 block rounded-xl bg-indigo-600 px-5 py-3 text-center font-semibold text-white hover:bg-indigo-500">Sign in to subscribe</a>
        ) : isPro ? (
          <button type="button" disabled={busy} onClick={() => openBilling("/api/billing/portal/")} className="mt-6 w-full rounded-xl border border-slate-600 px-5 py-3 font-semibold text-white hover:bg-slate-800 disabled:opacity-60">
            {busy ? "Opening…" : "Manage subscription"}
          </button>
        ) : (
          <button type="button" disabled={busy || billing?.configured === false} onClick={() => openBilling("/api/billing/checkout/")} className="mt-6 w-full rounded-xl bg-indigo-600 px-5 py-3 font-semibold text-white hover:bg-indigo-500 disabled:opacity-60">
            {busy ? "Opening secure checkout…" : "Subscribe with Stripe"}
          </button>
        )}
        <p className="mt-4 text-center text-xs leading-5 text-slate-500">Research and education only—not individualized investment advice. Options can lose their entire value.</p>
      </div>
    </div>
  );
}
