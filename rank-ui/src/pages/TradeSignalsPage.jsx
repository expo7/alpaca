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

function dateOnly(value) {
  if (!value) return "—";
  return new Date(`${value}T12:00:00`).toLocaleDateString([], { dateStyle: "medium" });
}

function plannedPercent(value, entryReference) {
  if (value === null || value === undefined || !entryReference) return null;
  return ((Number(value) / entryReference) - 1) * 100;
}

function PlanValue({ value, entryReference, tone = "text-white" }) {
  const change = plannedPercent(value, entryReference);
  return (
    <div className={`mt-1 font-semibold ${tone}`}>
      {money(value)}
      {change !== null && <span className="ml-1.5 text-xs font-medium text-slate-500">{percent(change)}</span>}
    </div>
  );
}

function CurrentQuote({ signal }) {
  const [quote, setQuote] = useState(null);

  useEffect(() => {
    let cancelled = false;
    fetch(`/api/trade-signals/${signal.id}/quote/`)
      .then((response) => response.ok ? response.json() : Promise.reject(new Error("Quote unavailable")))
      .then((data) => { if (!cancelled) setQuote(data); })
      .catch(() => { if (!cancelled) setQuote({ available: false, status_label: "Quote unavailable" }); });
    return () => { cancelled = true; };
  }, [signal.id]);

  const optionChange = quote?.option_midpoint && signal.actual_entry
    ? plannedPercent(quote.option_midpoint, Number(signal.actual_entry))
    : null;

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/45 p-4">
      <div className="flex items-center justify-between gap-3">
        <div className="text-xs font-bold uppercase tracking-[0.16em] text-slate-500">Market now</div>
        <div className={`text-xs font-semibold ${quote?.available ? "text-amber-300" : "text-slate-500"}`}>
          {quote?.status_label || "Loading quote…"}
        </div>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div><div className="text-xs text-slate-500">{signal.symbol} last</div><div className="mt-1 font-semibold text-white">{money(quote?.underlying_price)}</div></div>
        {signal.instrument_type !== "stock" && <>
          <div><div className="text-xs text-slate-500">Option bid / ask</div><div className="mt-1 font-semibold text-white">{money(quote?.option_bid)} / {money(quote?.option_ask)}</div></div>
          <div><div className="text-xs text-slate-500">Midpoint</div><div className="mt-1 font-semibold text-white">{money(quote?.option_midpoint)}{optionChange !== null && <span className={`ml-1.5 text-xs ${optionChange >= 0 ? "text-emerald-400" : "text-rose-400"}`}>{percent(optionChange)}</span>}</div></div>
          <div><div className="text-xs text-slate-500">Spread / OI</div><div className="mt-1 font-semibold text-white">{quote?.spread_pct != null ? `${Number(quote.spread_pct).toFixed(1)}%` : "—"} / {quote?.option_open_interest ?? "—"}</div></div>
        </>}
      </div>
      <div className="mt-3 text-xs text-slate-600">
        {quote?.source || "Yahoo Finance (delayed)"} · {quote?.market_quote_at ? dateTime(quote.market_quote_at) : quote?.fetched_at ? `Checked ${dateTime(quote.fetched_at)}` : "Awaiting quote"}
      </div>
    </div>
  );
}

function TradeCard({ signal, archived = false }) {
  const entry = signal.entry_high && signal.entry_high !== signal.entry_low
    ? `${money(signal.entry_low)}–${money(signal.entry_high)}`
    : money(signal.entry_low);
  const latest = signal.updates?.[signal.updates.length - 1];
  const returnValue = signal.realized_return_pct ?? signal.max_return_pct;
  const positive = Number(returnValue) >= 0;
  const entryReference = signal.actual_entry
    ? Number(signal.actual_entry)
    : signal.entry_high
      ? (Number(signal.entry_low) + Number(signal.entry_high)) / 2
      : Number(signal.entry_low);
  const hasPublicationQuote = signal.publication_underlying_price || signal.publication_option_bid || signal.publication_option_ask;

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
              {signal.paper_execution_enabled && (
                <span className="rounded-full border border-sky-700/60 bg-sky-950/40 px-2.5 py-1 text-xs font-semibold text-sky-300">
                  Alpaca paper · {signal.paper_quantity} {Number(signal.paper_quantity) === 1 ? "contract" : "contracts"}
                </span>
              )}
            </div>
            {signal.company_name && <p className="mt-1 text-slate-400">{signal.company_name}</p>}
          </div>
          <div className="text-right text-sm text-slate-500">
            <div>Published</div>
            <time>{dateTime(signal.published_at)}</time>
          </div>
        </div>

        {signal.underlying_trigger_price && (
          <div className="mt-5 rounded-xl border border-indigo-500/35 bg-indigo-950/25 p-4">
            <div className="text-xs font-bold uppercase tracking-[0.16em] text-indigo-300">Entry trigger</div>
            <div className="mt-2 flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <span className="text-lg font-bold text-white">{signal.symbol} {signal.trigger_direction === "below" ? "below" : "above"} {money(signal.underlying_trigger_price)}</span>
              {signal.trigger_confirmation && <span className="text-sm text-slate-300">{signal.trigger_confirmation}</span>}
            </div>
            <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-sm text-slate-400">
              {signal.do_not_chase_price && <span>Do not chase option above <strong className="text-slate-200">{money(signal.do_not_chase_price)}</strong></span>}
              {signal.entry_deadline && <span>Entry deadline <strong className="text-slate-200">{dateOnly(signal.entry_deadline)}</strong></span>}
              <span>Official fill: <strong className="text-slate-200">{signal.official_fill_method === "midpoint" ? "midpoint at activation" : "ask at activation"}</strong></span>
            </div>
          </div>
        )}

        <div className="mt-5 grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
          <div><div className="text-xs uppercase tracking-wide text-slate-500">{signal.instrument_type === "stock" ? "Share entry plan" : "Option entry plan"}</div><div className="mt-1 font-semibold text-white">{entry}</div>{signal.instrument_type !== "stock" && <div className="mt-0.5 text-xs text-slate-600">premium per share</div>}</div>
          <div><div className="text-xs uppercase tracking-wide text-slate-500">Initial stop</div><PlanValue value={signal.initial_stop} entryReference={entryReference} tone="text-rose-300" /></div>
          <div><div className="text-xs uppercase tracking-wide text-slate-500">Target 1</div><PlanValue value={signal.target_1} entryReference={entryReference} tone="text-emerald-300" /></div>
          <div><div className="text-xs uppercase tracking-wide text-slate-500">Targets 2 / 3</div><div className="flex flex-wrap gap-x-2"><PlanValue value={signal.target_2} entryReference={entryReference} tone="text-emerald-300" /><PlanValue value={signal.target_3} entryReference={entryReference} tone="text-emerald-300" /></div></div>
        </div>

        {!archived && <div className="mt-5"><CurrentQuote signal={signal} /></div>}

        <div className="mt-4 rounded-xl border border-slate-800 bg-slate-950/25 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="text-xs font-bold uppercase tracking-[0.16em] text-slate-500">At publication</div>
            <div className="font-mono text-xs text-slate-600">{signal.contract_symbol}</div>
          </div>
          {hasPublicationQuote ? (
            <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
              <div><div className="text-xs text-slate-500">{signal.symbol} price</div><div className="mt-1 font-semibold text-slate-200">{money(signal.publication_underlying_price)}</div></div>
              <div><div className="text-xs text-slate-500">Option bid / ask</div><div className="mt-1 font-semibold text-slate-200">{money(signal.publication_option_bid)} / {money(signal.publication_option_ask)}</div></div>
              <div><div className="text-xs text-slate-500">Spread / volume / OI</div><div className="mt-1 font-semibold text-slate-200">{signal.publication_option_spread_pct != null ? `${Number(signal.publication_option_spread_pct).toFixed(1)}%` : "—"} / {signal.publication_option_volume ?? "—"} / {signal.publication_option_open_interest ?? "—"}</div></div>
              <div><div className="text-xs text-slate-500">Quote captured</div><div className="mt-1 font-semibold text-slate-200">{dateTime(signal.publication_quote_at)}</div></div>
            </div>
          ) : (
            <p className="mt-2 text-sm text-slate-500">A market quote was not captured with this publication.</p>
          )}
          {signal.publication_quote_source && <div className="mt-2 text-xs text-slate-600">{signal.publication_quote_source}</div>}
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
          <h2 className="text-xl font-semibold text-white">No setups published yet</h2>
          <p className="mx-auto mt-2 max-w-xl text-slate-400">The first staff-reviewed setup will appear here with its original entry plan, risk level, targets, and timestamp.</p>
        </div>
      )}

      {!!active.length && <section><h2 className="mb-3 text-lg font-semibold text-white">Active setups</h2><div className="space-y-4">{active.map((signal) => <TradeCard key={signal.id} signal={signal} />)}</div></section>}
      {!!history.length && <section className="mt-8"><h2 className="mb-3 text-lg font-semibold text-white">Past performance <span className="ml-1 text-sm font-normal text-slate-500">{history.length}</span></h2><div className="space-y-4">{history.map((signal) => <TradeCard key={signal.id} signal={signal} archived />)}</div></section>}

      <p className="mt-8 border-t border-slate-800 pt-5 text-xs leading-5 text-slate-500">For research and educational use only. Options can lose their entire value. Published performance does not include commissions, slippage, taxes, or differences in execution unless a record specifically says otherwise.</p>
    </div>
  );
}
