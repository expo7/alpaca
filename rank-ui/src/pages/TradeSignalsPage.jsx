import { useEffect, useMemo, useState } from "react";

const ACTIVE = new Set(["published", "open"]);

function money(value) {
  if (value === null || value === undefined || value === "") return "—";
  return `$${Number(value).toFixed(2)}`;
}

function percent(value) {
  if (value === null || value === undefined || value === "") return "—";
  const number = Number(value);
  return `${number > 0 ? "+" : ""}${number.toFixed(2)}%`;
}

function dateTime(value) {
  if (!value) return "—";
  return new Date(value).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
}

function TradeCard({ signal, archived = false }) {
  const entry = signal.entry_high && signal.entry_high !== signal.entry_low
    ? `${money(signal.entry_low)}–${money(signal.entry_high)}`
    : money(signal.entry_low);
  const latest = signal.updates?.[signal.updates.length - 1];
  const returnValue = signal.realized_return_pct ?? signal.max_return_pct;
  const positive = Number(returnValue) >= 0;

  return (
    <article className={`overflow-hidden rounded-2xl border ${archived ? "border-slate-700 bg-slate-900/65" : "border-indigo-500/40 bg-slate-900"}`}>
      <div className={`h-1 ${archived ? "bg-slate-600" : signal.instrument_type === "put" ? "bg-rose-500" : "bg-emerald-500"}`} />
      <div className="p-4 sm:p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-xl font-bold text-white">{signal.instrument}</h2>
              <span className={`rounded-full px-2.5 py-1 text-xs font-bold uppercase tracking-wide ${signal.status === "open" ? "bg-emerald-950 text-emerald-300" : signal.status === "published" ? "bg-indigo-950 text-indigo-300" : "bg-slate-800 text-slate-300"}`}>
                {signal.status_label}
              </span>
              <span className="rounded-full border border-amber-700/60 px-2.5 py-1 text-xs font-semibold capitalize text-amber-300">
                {signal.risk_level} risk
              </span>
            </div>
            {signal.company_name && <p className="mt-1 text-slate-400">{signal.company_name}</p>}
          </div>
          <div className="text-right text-sm text-slate-500">
            <div>Published</div>
            <time>{dateTime(signal.published_at)}</time>
          </div>
        </div>

        <div className="mt-5 grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
          <div><div className="text-xs uppercase tracking-wide text-slate-500">Entry plan</div><div className="mt-1 font-semibold text-white">{entry}</div></div>
          <div><div className="text-xs uppercase tracking-wide text-slate-500">Initial stop</div><div className="mt-1 font-semibold text-rose-300">{money(signal.initial_stop)}</div></div>
          <div><div className="text-xs uppercase tracking-wide text-slate-500">Target 1</div><div className="mt-1 font-semibold text-emerald-300">{money(signal.target_1)}</div></div>
          <div><div className="text-xs uppercase tracking-wide text-slate-500">Target 2 / 3</div><div className="mt-1 font-semibold text-emerald-300">{[signal.target_2, signal.target_3].filter(Boolean).map(money).join(" / ") || "—"}</div></div>
        </div>

        <div className="mt-5 rounded-xl bg-slate-950/55 p-4">
          <div className="text-xs font-bold uppercase tracking-[0.16em] text-slate-500">Why it qualified</div>
          <p className="mt-2 leading-6 text-slate-200">{signal.thesis}</p>
          {!!signal.evidence_tags?.length && (
            <div className="mt-3 flex flex-wrap gap-2">
              {signal.evidence_tags.map((tag) => <span key={tag} className="rounded-lg bg-indigo-950/70 px-2.5 py-1 text-xs font-semibold text-indigo-200">{tag}</span>)}
            </div>
          )}
        </div>

        {signal.invalidation && <p className="mt-3 text-sm text-slate-400"><span className="font-semibold text-slate-300">Invalidation:</span> {signal.invalidation}</p>}

        {latest && (
          <div className="mt-4 border-l-2 border-indigo-500 pl-3">
            <div className="text-xs uppercase tracking-wide text-slate-500">Latest update · {dateTime(latest.occurred_at)}</div>
            <p className="mt-1 text-sm text-slate-200">{latest.note}</p>
          </div>
        )}

        {archived && returnValue !== null && returnValue !== undefined && (
          <div className="mt-4 flex items-center justify-between border-t border-slate-800 pt-4">
            <span className="text-sm text-slate-400">Recorded return</span>
            <span className={`text-xl font-bold ${positive ? "text-emerald-400" : "text-rose-400"}`}>{percent(returnValue)}</span>
          </div>
        )}
      </div>
    </article>
  );
}

export default function TradeSignalsPage() {
  const [signals, setSignals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    fetch("/api/trade-signals/")
      .then((response) => {
        if (!response.ok) throw new Error("Unable to load the trade record.");
        return response.json();
      })
      .then((data) => { if (!cancelled) setSignals(Array.isArray(data) ? data : []); })
      .catch((err) => { if (!cancelled) setError(err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  const active = useMemo(() => signals.filter((signal) => ACTIVE.has(signal.status)), [signals]);
  const history = useMemo(() => signals.filter((signal) => !ACTIVE.has(signal.status)), [signals]);

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="text-xs font-bold uppercase tracking-[0.18em] text-indigo-300">Quantelle trade record</div>
          <h1 className="mt-2 text-3xl font-bold text-white">Published trade setups</h1>
          <p className="mt-2 max-w-2xl text-slate-400">Every setup is timestamped before its outcome is known. Entries, stops, targets, changes, wins, and losses remain on the record.</p>
        </div>
        <div className="rounded-xl border border-slate-700 bg-slate-900 px-4 py-3 text-sm text-slate-300">
          {signals.length} published · {active.length} active
        </div>
      </div>

      {loading && <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-8 text-center text-slate-400">Loading trade record…</div>}
      {error && <div className="rounded-2xl border border-rose-800 bg-rose-950/40 p-5 text-rose-200">{error}</div>}
      {!loading && !error && !signals.length && (
        <div className="rounded-2xl border border-dashed border-slate-700 bg-slate-900/40 p-8 text-center">
          <h2 className="text-xl font-semibold text-white">The record starts Monday</h2>
          <p className="mx-auto mt-2 max-w-xl text-slate-400">The first staff-reviewed setup will appear here with its original entry plan, risk level, targets, and timestamp.</p>
        </div>
      )}

      {!!active.length && <section><h2 className="mb-3 text-lg font-semibold text-white">Active setups</h2><div className="space-y-4">{active.map((signal) => <TradeCard key={signal.id} signal={signal} />)}</div></section>}
      {!!history.length && <section className="mt-8"><h2 className="mb-3 text-lg font-semibold text-white">Past performance <span className="ml-1 text-sm font-normal text-slate-500">{history.length}</span></h2><div className="space-y-4">{history.map((signal) => <TradeCard key={signal.id} signal={signal} archived />)}</div></section>}

      <p className="mt-8 border-t border-slate-800 pt-5 text-xs leading-5 text-slate-500">For research and educational use only. Options can lose their entire value. Published performance does not include commissions, slippage, taxes, or differences in execution unless a record specifically says otherwise.</p>
    </div>
  );
}
