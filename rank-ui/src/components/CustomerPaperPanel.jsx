import { useEffect, useState } from "react";

export default function CustomerPaperPanel({ token }) {
  const [connection, setConnection] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!token) return;
    let active = true;
    fetch("/api/alpaca-paper/connection/", { headers: { Authorization: `Bearer ${token}` } })
      .then((response) => response.ok ? response.json() : null)
      .then((data) => { if (active) setConnection(data); })
      .catch(() => {});
    return () => { active = false; };
  }, [token]);

  if (!connection) return null;

  async function connect() {
    setBusy(true);
    setError("");
    try {
      const response = await fetch("/api/alpaca-paper/connect/", { method: "POST", headers: { Authorization: `Bearer ${token}` } });
      if (!response.ok) throw new Error("Connection is unavailable. Please try again later.");
      const data = await response.json();
      window.location.assign(data.authorize_url);
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  async function disconnect() {
    setBusy(true);
    setError("");
    try {
      const response = await fetch("/api/alpaca-paper/connection/", { method: "DELETE", headers: { Authorization: `Bearer ${token}` } });
      if (!response.ok) throw new Error("Could not disconnect your paper account.");
      setConnection({ ...connection, connected: false, account_suffix: null });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return <aside className="mb-6 rounded-2xl border border-indigo-500/35 bg-indigo-950/25 p-5">
    <h2 className="text-lg font-bold text-white">Alpaca account integration</h2>
    <p className="mt-1 text-sm text-slate-300">Staff preview · existing Alpaca paper users can authorize a read-only connection after app approval. Quantelle-first account opening and individual paper orders are planned separately. No customer or live orders can be placed here.</p>
    {!connection.available && <p role="status" className="mt-3 rounded-lg border border-amber-500/40 bg-amber-950/30 p-3 text-sm text-amber-100">Connection is awaiting Alpaca app approval, server credentials, and a staff paper-account test.</p>}
    <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-300"><span className="rounded-full border border-slate-600 px-2 py-1">Connect · read-only</span><span className="rounded-full border border-slate-600 px-2 py-1">Broker API · review</span><span className="rounded-full border border-slate-600 px-2 py-1">Paper orders · disabled</span><span className="rounded-full border border-slate-600 px-2 py-1">Live money · disabled</span></div>
    {!connection.available ? null : connection.connected ? <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-slate-200">
      <span>Connected paper account ending {connection.account_suffix}</span>
      <button type="button" disabled={busy} onClick={disconnect} className="rounded-lg border border-slate-500 px-3 py-2 font-semibold hover:bg-slate-800 disabled:opacity-50">Disconnect</button>
    </div> : <div className="mt-3 flex flex-wrap items-center gap-3 text-sm">
      <a href="https://app.alpaca.markets/signup" target="_blank" rel="noreferrer" className="font-semibold text-indigo-200 underline">Create a paper account at Alpaca</a>
      <button type="button" disabled={busy} onClick={connect} className="rounded-lg bg-indigo-500 px-4 py-2 font-semibold text-white hover:bg-indigo-400 disabled:opacity-50">Connect paper account</button>
    </div>}
    {error && <p role="alert" className="mt-3 text-sm text-rose-300">{error}</p>}
  </aside>;
}
