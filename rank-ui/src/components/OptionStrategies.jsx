import { useEffect, useState } from "react";

const cash = (v) => v == null ? "—" : new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(v));
const when = (v) => v ? new Date(v).toLocaleString("en-US", { timeZone: "America/Phoenix" }) + " MST" : "Not checked yet";
const active = new Set(["pending", "entering", "open", "closing", "blocked"]);

export default function OptionStrategies() {
  const [rows, setRows] = useState([]);
  const [error, setError] = useState("");
  const [view, setView] = useState("active");
  useEffect(() => {
    const controller = new AbortController();
    const refresh = async () => {
      try {
        const response = await fetch("/api/option-strategies/", { signal: controller.signal });
        if (!response.ok) throw new Error("Complex strategy records are unavailable.");
        const data = await response.json();
        setRows(Array.isArray(data.strategies) ? data.strategies : []);
        setError("");
      } catch (e) {
        if (e.name !== "AbortError") setError(e.message);
      }
    };
    refresh();
    const timer = window.setInterval(refresh, 30000);
    return () => { controller.abort(); window.clearInterval(timer); };
  }, []);
  const shown = rows.filter(r => view === "all" || (view === "completed" ? r.state === "closed" : active.has(r.state)));
  return <section className="mb-6 rounded-2xl border border-indigo-800/50 bg-slate-900/60 p-5" aria-label="Complex paper strategies">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div><h2 className="text-xl font-bold text-white">Complex paper strategies</h2><p className="mt-1 text-sm text-slate-400">Spreads, condors and time spreads · one strategy unit · all legs managed together</p></div>
      <div className="flex gap-2">{["active", "completed", "all"].map(v => <button key={v} type="button" aria-pressed={view === v} onClick={() => setView(v)} className={`rounded-lg px-3 py-2 text-sm capitalize ${view === v ? "bg-indigo-600 text-white" : "bg-slate-800 text-slate-300"}`}>{v}</button>)}</div>
    </div>
    {error && <p role="alert" className="mt-4 text-amber-300">{error}</p>}
    {!error && shown.length === 0 && <p className="mt-4 text-sm text-slate-400">No {view === "all" ? "published" : view} complex strategies recorded.</p>}
    <div className="mt-4 space-y-4">{shown.map(r => <article id={`strategy-${r.id}`} key={r.id} className="rounded-xl border border-slate-700 p-4">
      <div className="flex flex-wrap justify-between gap-2"><h3 className="font-bold text-white">{r.symbol} · {r.kind.replaceAll("_", " ")} · PAPER #{r.id}</h3><strong className="text-indigo-300">{r.state.toUpperCase()}</strong></div>
      <ul className="mt-3 space-y-1 font-mono text-sm text-slate-200">{r.legs.map(l => <li key={l.symbol}>{l.side.toUpperCase()} 1 {l.symbol}</li>)}</ul>
      <div className="mt-3 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
        <div className="text-slate-400">Net entry limit<div className="text-white">{cash(r.entry_limit)} {Number(r.entry_limit) < 0 ? "credit" : "debit"}</div></div>
        <div className="text-slate-400">Actual net entry<div className="text-white">{cash(r.entry_fill)}</div></div>
        <div className="text-slate-400">{r.state === "closed" ? "Realized paper P/L" : "Indicative paper P/L"}<div className="text-white">{cash(r.state === "closed" ? r.realized_pl : r.quote?.unrealized_pl)}</div></div>
        <div className="text-slate-400">Risk bound<div className="text-white">{cash(r.risk.max_loss_dollars)}</div></div>
      </div>
      <p className="mt-3 text-sm text-slate-300">Monitored dollar stop {cash(r.stop_loss_dollars)} · profit target {cash(r.take_profit_dollars)} · close all legs by {when(r.close_by)}</p>
      <p className="mt-2 text-xs text-amber-200">{r.protection}. {r.risk.basis}</p>
      {r.management_session === "closed" && <p className="mt-2 text-sm text-slate-400">Market closed; monitoring resumes at the next regular session. P/L reflects the last stored quote.</p>}
      {r.management_attention && <p className="mt-2 text-sm font-semibold text-amber-300">Management needs operator attention. Review the latest run report.</p>}
      <p className="mt-3 text-sm text-slate-200">{r.thesis}</p>
      <details className="mt-3 text-sm text-slate-400"><summary className="cursor-pointer">Invalidation, quotes and lifecycle</summary>
        <p className="mt-2">{r.invalidation}</p><p className="mt-2">Last management check: {when(r.checked_at)}</p>
        <p>Quote source: {r.quote?.source || "Unavailable"} · fetched {when(r.quote?.fetched_at)}</p>
        <ul className="mt-2">{Object.entries(r.quote?.legs || {}).map(([symbol, q]) => <li key={symbol}>{symbol}: {cash(q.bid)} / {cash(q.ask)} · {when(q.at)}</li>)}</ul>
        <ul className="mt-2 space-y-1">{r.events.map((e, i) => <li key={`${e.kind}-${e.at}-${i}`}>{when(e.at)} · {e.kind} · alert {e.notification_status}</li>)}</ul>
      </details>
    </article>)}</div>
  </section>;
}
