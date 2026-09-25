import { useEffect, useMemo, useState } from "react";

const ACTIVE = new Set(["published", "open"]);

function money(value) {
  if (value === null || value === undefined || value === "") return "—";
  const number = Number(value);
  return `${number < 0 ? "−" : ""}$${Math.abs(number).toFixed(2)}`;
}

function percent(value) {
  if (value === null || value === undefined || value === "") return "—";
  const number = Number(value);
  return `${number > 0 ? "+" : ""}${number.toFixed(2)}%`;
}

function dateTime(value) {
  if (!value) return "—";
  return `${new Date(value).toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short", timeZone: "America/Phoenix" })} MST`;
}

function dateOnly(value) {
  if (!value) return "—";
  return new Date(`${value}T12:00:00`).toLocaleDateString([], { dateStyle: "medium" });
}

function plannedPercent(value, entryReference) {
  if (value === null || value === undefined || !entryReference) return null;
  return ((Number(value) / entryReference) - 1) * 100;
}

const EVIDENCE_LABELS = {
  "price action": { label: "Technical confirmation", explanation: "Published price-action evidence" },
  "technical analysis": { label: "Technical confirmation", explanation: "Published technical-analysis evidence" },
  "options flow": { label: "Options flow", explanation: "Published options-flow evidence; this is not a standalone recommendation" },
  "bull sweeps": { label: "Bullish flow", explanation: "Published bullish options-flow evidence" },
  "bear sweeps": { label: "Bearish flow", explanation: "Published bearish options-flow evidence" },
};

function EvidenceTags({ tags = [] }) {
  return <div className="mt-3 flex flex-wrap gap-2">{tags.map((tag, index) => {
    const mapped = EVIDENCE_LABELS[String(tag).trim().toLowerCase()];
    return <span key={`${tag}-${index}`} title={mapped?.explanation || `Published evidence: ${tag}`} className="rounded-lg border border-indigo-800/50 bg-indigo-950/70 px-2.5 py-1 text-xs font-semibold text-indigo-200">{mapped?.label || tag}</span>;
  })}</div>;
}

function customerEvents(signal) {
  return (signal.updates || []).filter((update) => update.audience !== "staff");
}

function ActivityStream({ events, heading = "Customer activity", onSelectTrade }) {
  return <div className="rounded-2xl border border-slate-800 bg-slate-900/50 p-4 sm:p-5">
    <h3 className="font-semibold text-white">{heading}</h3>
    {events.length ? <ol className="mt-4 space-y-4 border-l border-indigo-600/50 pl-4">{events.map(({ signal, update }) =>
      <li key={`${signal.id}-${update.id}`} className="relative text-sm">
        <span aria-hidden="true" className="absolute -left-[1.27rem] top-1.5 h-2 w-2 rounded-full bg-indigo-400" />
        <div className="flex flex-wrap items-baseline gap-x-2"><strong className="text-slate-100">{signal.symbol} · {update.event_label || update.event_type || "Update"}</strong><time className="text-xs text-slate-500">{dateTime(update.occurred_at)}</time></div>
        <p className="mt-1 whitespace-pre-wrap text-slate-300">{update.note}</p>
        {onSelectTrade ? <button type="button" onClick={() => onSelectTrade(signal.id)} className="mt-1 text-xs font-semibold text-indigo-300 hover:text-indigo-200">View trade card</button>
          : <a href={`#trade-${signal.id}`} className="mt-1 inline-block text-xs font-semibold text-indigo-300 hover:text-indigo-200">View trade card</a>}
      </li>)}</ol> : <p className="mt-3 text-sm text-slate-400">No customer updates are recorded yet.</p>}
  </div>;
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

function CurrentQuote({ signal, token = "" }) {
  const [quote, setQuote] = useState(null);

  useEffect(() => {
    let cancelled = false;
    const loadQuote = () => {
      fetch(`/api/trade-signals/${signal.id}/quote/`, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
        .then((response) => response.ok ? response.json() : Promise.reject(new Error("Quote unavailable")))
        .then((data) => { if (!cancelled) setQuote(data); })
        .catch(() => { if (!cancelled) setQuote({ available: false, status_label: "Quote unavailable" }); });
    };
    loadQuote();
    const interval = window.setInterval(loadQuote, 60_000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [signal.id, token]);

  const optionChange = quote?.option_midpoint && signal.actual_entry
    ? plannedPercent(quote.option_midpoint, Number(signal.actual_entry))
    : null;
  const position = quote?.paper_position;
  const positionPositive = Number(position?.unrealized_pl) >= 0;
  const stop = Number(signal.current_stop || signal.initial_stop);
  const target = Number(signal.target_1);
  const bid = Number(quote?.option_bid);
  const targetProgress = signal.status === "open" && quote?.option_bid != null && target > stop
    ? Math.max(0, Math.min(100, ((bid - stop) / (target - stop)) * 100)) : null;

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/45 p-4">
      <div className="flex items-center justify-between gap-3">
        <div className="text-xs font-bold uppercase tracking-[0.16em] text-slate-500">Latest available quote</div>
        <div className={`text-xs font-semibold ${quote?.available ? "text-amber-300" : "text-slate-500"}`}>
          {quote?.status_label || "Loading quote…"}
        </div>
      </div>
      {targetProgress !== null && <div className="mt-4"><div className="flex justify-between text-xs text-slate-400"><span>Bid progress from stop to target 1</span><span>{targetProgress.toFixed(0)}%</span></div><div role="progressbar" aria-label="Bid progress to target 1" aria-valuenow={Math.round(targetProgress)} aria-valuemin={0} aria-valuemax={100} className="mt-2 h-2 overflow-hidden rounded-full bg-slate-800"><div className="h-full rounded-full bg-indigo-400" style={{ width: `${targetProgress}%` }} /></div></div>}
      <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div><div className="text-xs text-slate-500">{signal.symbol} last</div><div className="mt-1 font-semibold text-white">{money(quote?.underlying_price)}</div></div>
        {signal.instrument_type !== "stock" && <>
          <div><div className="text-xs text-slate-500">Option bid / ask</div><div className="mt-1 font-semibold text-white">{money(quote?.option_bid)} / {money(quote?.option_ask)}</div></div>
          <div><div className="text-xs text-slate-500">{quote?.option_price_label || "Midpoint"}</div><div className="mt-1 font-semibold text-white">{money(quote?.option_midpoint)}{optionChange !== null && <span className={`ml-1.5 text-xs ${optionChange >= 0 ? "text-emerald-400" : "text-rose-400"}`}>{percent(optionChange)}</span>}</div></div>
          <div><div className="text-xs text-slate-500">Spread / OI</div><div className="mt-1 font-semibold text-white">{quote?.spread_pct != null ? `${Number(quote.spread_pct).toFixed(1)}%` : "—"} / {quote?.option_open_interest ?? "—"}</div></div>
        </>}
      </div>
      {position?.available && (
        <div className="mt-4 rounded-xl border border-sky-800/60 bg-sky-950/25 p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="text-xs font-bold uppercase tracking-[0.16em] text-sky-300">Alpaca paper position</div>
            <div className={`text-lg font-bold ${positionPositive ? "text-emerald-400" : "text-rose-400"}`}>
              {money(position.unrealized_pl)} <span className="text-sm">({percent(position.unrealized_pl_pct)})</span>
            </div>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
            <div><div className="text-xs text-slate-500">Quantity</div><div className="mt-1 font-semibold text-slate-200">{position.quantity ?? "—"}</div></div>
            <div><div className="text-xs text-slate-500">Average fill</div><div className="mt-1 font-semibold text-slate-200">{money(position.average_entry_price)}</div></div>
            <div><div className="text-xs text-slate-500">Alpaca price</div><div className="mt-1 font-semibold text-slate-200">{money(position.current_price)}</div></div>
            <div><div className="text-xs text-slate-500">Market value</div><div className="mt-1 font-semibold text-slate-200">{money(position.market_value)}</div></div>
          </div>
          <div className="mt-2 text-xs text-slate-600">Unrealized P/L · paper account · checked {dateTime(position.fetched_at)}</div>
        </div>
      )}
      <div className="mt-3 text-xs text-slate-600">
        {quote?.source || "Yahoo Finance (delayed)"} · {quote?.market_quote_at ? dateTime(quote.market_quote_at) : quote?.fetched_at ? `Checked ${dateTime(quote.fetched_at)}` : "Awaiting quote"}
      </div>
    </div>
  );
}

function TradeCard({ signal, archived = false, onUpgrade, token = "" }) {
  if (signal.is_locked) {
    return (
      <article id={`trade-${signal.id}`} className="scroll-mt-28 overflow-hidden rounded-2xl border border-indigo-500/40 bg-slate-900">
        <div className="h-1 bg-indigo-500" />
        <div className="p-5 sm:p-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div><h2 className="text-xl font-bold text-white">Active {signal.symbol} setup</h2><p className="mt-1 text-slate-400">{signal.company_name} · {signal.instrument_type === "put" ? "Put" : "Call"} option</p></div>
            <span className="rounded-full bg-indigo-950 px-2.5 py-1 text-xs font-bold uppercase tracking-wide text-indigo-300">Pro setup</span>
          </div>
          <p className="mt-5 max-w-2xl leading-7 text-slate-300">The contract, trigger, entry range, risk controls, live quote, thesis, and evidence are available to Quantelle Pro subscribers. The complete result will remain on the public record when the setup ends.</p>
          <button type="button" onClick={onUpgrade} className="mt-5 rounded-xl bg-indigo-600 px-5 py-2.5 font-semibold text-white hover:bg-indigo-500">View Quantelle Pro</button>
        </div>
      </article>
    );
  }
  const entry = signal.entry_high && signal.entry_high !== signal.entry_low
    ? `${money(signal.entry_low)}–${money(signal.entry_high)}`
    : money(signal.entry_low);
  const customerUpdates = customerEvents(signal);
  const latest = customerUpdates[customerUpdates.length - 1];
  const isPending = signal.status === "published";
  const isOpen = signal.status === "open";
  const returnValue = signal.realized_return_pct;
  const positive = Number(returnValue) >= 0;
  const grossPaperResult = signal.paper_execution_enabled && signal.actual_entry != null && signal.final_exit != null
    ? (Number(signal.final_exit) - Number(signal.actual_entry)) * 100 * Number(signal.paper_quantity || 1)
    : null;
  const entryReference = signal.actual_entry
    ? Number(signal.actual_entry)
    : signal.entry_high
      ? (Number(signal.entry_low) + Number(signal.entry_high)) / 2
      : Number(signal.entry_low);
  const hasPublicationQuote = signal.publication_underlying_price || signal.publication_option_bid || signal.publication_option_ask;

  return (
    <article id={`trade-${signal.id}`} className={`scroll-mt-28 overflow-hidden rounded-2xl border ${archived ? "border-slate-700 bg-slate-900/65" : "border-indigo-500/40 bg-slate-900"}`}>
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

        {isOpen && <div className="mt-5 grid grid-cols-2 gap-3 rounded-xl border border-sky-800/60 bg-sky-950/25 p-4 text-sm sm:grid-cols-4">
          <div><div className="text-xs text-slate-400">Average fill</div><strong>{money(signal.actual_entry)}</strong></div>
          <div><div className="text-xs text-slate-400">Current stop</div><strong>{money(signal.current_stop || signal.initial_stop)}</strong></div>
          <div><div className="text-xs text-slate-400">Target 1</div><strong>{money(signal.target_1)}</strong></div>
          <div><div className="text-xs text-slate-400">{signal.protection?.verified ? "Verified broker protection" : "Broker protection · verification pending"}</div><strong>{signal.protection ? `${signal.protection.type === "broker_target" ? "Target limit" : "Stop"} ${money(signal.protection.price)}` : "No protective order confirmed"}</strong>{signal.protection?.verified_at && <div className="mt-1 text-xs text-slate-400">Checked {dateTime(signal.protection.verified_at)}</div>}</div>
        </div>}
        {signal.underlying_trigger_price && (
          <details open={isPending} className="mt-5 rounded-xl border border-indigo-500/35 bg-indigo-950/25 p-4">
            <summary className="cursor-pointer text-xs font-bold uppercase tracking-[0.16em] text-indigo-300">{isPending ? "Entry trigger" : "Original entry plan"}</summary>
            {!isPending && <div className="mt-3 text-sm text-slate-400">Entry range {entry} · Invalidation: {signal.invalidation || "—"}</div>}
            <div className="mt-2 flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <span className="text-lg font-bold text-white">{signal.symbol} {signal.trigger_direction === "below" ? "below" : "above"} {money(signal.underlying_trigger_price)}</span>
              {signal.trigger_confirmation && <span className="text-sm text-slate-300">{signal.trigger_confirmation}</span>}
            </div>
            <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-sm text-slate-400">
              {signal.do_not_chase_price && <span>Do not chase option above <strong className="text-slate-200">{money(signal.do_not_chase_price)}</strong></span>}
              {signal.entry_deadline && <span>Entry deadline <strong className="text-slate-200">{dateOnly(signal.entry_deadline)}</strong></span>}
              <span>Official fill: <strong className="text-slate-200">{signal.official_fill_method === "midpoint" ? "midpoint at activation" : "ask at activation"}</strong></span>
            </div>
          </details>
        )}

        <div className="mt-5 grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
          <div><div className="text-xs uppercase tracking-wide text-slate-500">{signal.instrument_type === "stock" ? "Share entry plan" : "Option entry plan"}</div><div className="mt-1 font-semibold text-white">{entry}</div>{signal.instrument_type !== "stock" && <div className="mt-0.5 text-xs text-slate-600">premium per share</div>}</div>
          <div><div className="text-xs uppercase tracking-wide text-slate-500">{isOpen ? "Current stop" : "Initial stop"}</div><PlanValue value={isOpen ? signal.current_stop || signal.initial_stop : signal.initial_stop} entryReference={entryReference} tone="text-rose-300" /></div>
          <div><div className="text-xs uppercase tracking-wide text-slate-500">Target 1</div><PlanValue value={signal.target_1} entryReference={entryReference} tone="text-emerald-300" /></div>
          <div><div className="text-xs uppercase tracking-wide text-slate-500">Targets 2 / 3</div><div className="flex flex-wrap gap-x-2"><PlanValue value={signal.target_2} entryReference={entryReference} tone="text-emerald-300" /><PlanValue value={signal.target_3} entryReference={entryReference} tone="text-emerald-300" /></div></div>
        </div>

        {!archived && <div className="mt-5"><CurrentQuote signal={signal} token={token} /></div>}

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
          {!!signal.evidence_tags?.length && <EvidenceTags tags={signal.evidence_tags} />}
        </div>

        {signal.invalidation && <p className="mt-3 text-sm text-slate-400"><span className="font-semibold text-slate-300">Invalidation:</span> {signal.invalidation}</p>}

        {latest && (
          <div className="mt-4 border-l-2 border-indigo-500 pl-3">
            <div className="text-xs uppercase tracking-wide text-slate-500">{isOpen && signal.protection?.verified_at && new Date(signal.protection.verified_at) > new Date(latest.occurred_at) ? "Earlier trade update" : "Latest trade update"} · {dateTime(latest.occurred_at)}</div>
            <p className="mt-1 text-sm text-slate-200">{latest.note}</p>
          </div>
        )}

        {customerUpdates.length > 1 && <details className="mt-4 rounded-xl border border-slate-800 p-3">
          <summary className="cursor-pointer font-semibold text-indigo-300">Customer activity · {customerUpdates.length} updates</summary>
          <div className="mt-4"><ActivityStream heading="Recorded customer updates" events={customerUpdates.map((update) => ({ signal, update }))} /></div>
        </details>}

        {archived && returnValue !== null && returnValue !== undefined && (
          <div className="mt-4 flex items-center justify-between border-t border-slate-800 pt-4">
            <span className="text-sm text-slate-400">Realized {signal.paper_execution_enabled ? "paper " : ""}return</span>
            <span className={`text-xl font-bold ${positive ? "text-emerald-400" : "text-rose-400"}`}>{percent(returnValue)}</span>
          </div>
        )}
        {archived && grossPaperResult !== null && <div className="mt-2 text-sm text-slate-300">Gross paper P/L: <strong className={grossPaperResult >= 0 ? "text-emerald-300" : "text-rose-300"}>{money(grossPaperResult)}</strong> <span className="text-xs text-slate-500">({signal.paper_quantity || 1} {(signal.paper_quantity || 1) === 1 ? "contract" : "contracts"} · before fees)</span></div>}
        {archived && <div className="mt-3 flex gap-6 text-sm text-slate-300"><span>Fill: {money(signal.actual_entry)}</span><span>Exit: {money(signal.final_exit)}</span></div>}
        {archived && <div className="mt-2 text-xs text-slate-400">Lifecycle certification: {signal.certification_state || "Pending"}{signal.paper_exit_reason ? ` · Exit: ${signal.paper_exit_reason.replaceAll("_", " ")}` : ""}</div>}
      </div>
    </article>
  );
}

export default function TradeSignalsPage({ token = "", onUpgrade = () => {} }) {
  const [signals, setSignals] = useState([]);
  const [view, setView] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    fetch("/api/trade-signals/", { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      .then((response) => {
        if (!response.ok) throw new Error("Unable to load the trade record.");
        return response.json();
      })
      .then((data) => { if (!cancelled) setSignals(Array.isArray(data) ? data : []); })
      .catch((err) => { if (!cancelled) setError(err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [token]);

  const pending = useMemo(() => signals.filter((signal) => signal.status === "published"), [signals]);
  const open = useMemo(() => signals.filter((signal) => signal.status === "open"), [signals]);
  const active = useMemo(() => signals.filter((signal) => ACTIVE.has(signal.status)), [signals]);
  const history = useMemo(() => signals.filter((signal) => !ACTIVE.has(signal.status)), [signals]);
  const activity = useMemo(() => signals.flatMap((signal) => customerEvents(signal).map((update) => ({ signal, update })))
    .sort((a, b) => new Date(b.update.occurred_at) - new Date(a.update.occurred_at)), [signals]);
  const views = [
    { id: "all", label: "All setups", count: signals.length },
    { id: "active", label: "Active", count: open.length },
    { id: "waiting", label: "Waiting", count: pending.length },
    { id: "completed", label: "Completed", count: history.length },
    { id: "activity", label: "All activity", count: activity.length },
  ];

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="text-xs font-bold uppercase tracking-[0.18em] text-indigo-300">Quantelle trade record</div>
          <h1 className="mt-2 text-3xl font-bold text-white">Published trade setups</h1>
          <p className="mt-2 max-w-2xl text-slate-400">Qualified options plans, monitored through their paper lifecycle. Every completed result, including a loss or unfilled entry, remains visible.</p>
        </div>
        <div className="rounded-xl border border-slate-700 bg-slate-900 px-4 py-3 text-sm text-slate-300">
          {signals.length} published · {open.length} active · {pending.length} waiting · {history.length} completed
        </div>
      </div>

      <aside className="mb-6 flex flex-col gap-4 rounded-2xl border border-sky-500/35 bg-sky-950/30 p-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="text-xs font-bold uppercase tracking-[0.16em] text-sky-300">Complimentary early access</div>
          <h2 className="mt-1 text-lg font-bold text-white">Get Quantelle trade alerts on Telegram</h2>
          <p className="mt-1 text-sm leading-6 text-slate-300">Receive alerts when a trade is opened, updated, or closed.</p>
        </div>
        <a
          href="https://t.me/+6zJGLH-XJWY0MTcx"
          target="_blank"
          rel="noreferrer"
          className="inline-flex shrink-0 items-center justify-center rounded-xl bg-sky-500 px-5 py-2.5 font-semibold text-slate-950 transition hover:bg-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-300 focus:ring-offset-2 focus:ring-offset-slate-950"
        >
          Join on Telegram
        </a>
      </aside>

      <nav aria-label="Trade record views" className="mb-6 flex gap-2 overflow-x-auto pb-2">
        {views.map((item) => <button key={item.id} type="button" aria-pressed={view === item.id} onClick={() => setView(item.id)}
          className={`min-h-11 shrink-0 rounded-xl border px-4 py-2 text-sm font-semibold transition ${view === item.id ? "border-indigo-400 bg-indigo-950 text-white" : "border-slate-700 bg-slate-900 text-slate-300 hover:border-slate-500"}`}>
          {item.label} <span className="ml-1 text-xs opacity-75">{item.count}</span>
        </button>)}
      </nav>

      {loading && <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-8 text-center text-slate-400">Loading trade record…</div>}
      {error && <div className="rounded-2xl border border-rose-800 bg-rose-950/40 p-5 text-rose-200">{error}</div>}
      {!loading && !error && !signals.length && (
        <div className="rounded-2xl border border-dashed border-slate-700 bg-slate-900/40 p-8 text-center">
          <h2 className="text-xl font-semibold text-white">No setups published yet</h2>
          <p className="mx-auto mt-2 max-w-xl text-slate-400">The first staff-reviewed setup will appear here with its original entry plan, risk level, targets, and timestamp.</p>
        </div>
      )}

      {!loading && !error && view === "activity" && <ActivityStream events={activity} heading="Customer trade activity" onSelectTrade={(id) => {
        setView("all");
        window.requestAnimationFrame(() => document.getElementById(`trade-${id}`)?.scrollIntoView());
      }} />}
      {!loading && !error && view === "active" && !open.length && <p className="rounded-xl border border-slate-800 bg-slate-900/50 p-6 text-slate-400">No active paper positions right now. Qualified setups are published only when their conditions are met.</p>}
      {!loading && !error && view === "waiting" && !pending.length && <p className="rounded-xl border border-slate-800 bg-slate-900/50 p-6 text-slate-400">No published setups are waiting for entry right now.</p>}
      {!loading && !error && view === "completed" && !history.length && <p className="rounded-xl border border-slate-800 bg-slate-900/50 p-6 text-slate-400">No completed setups yet.</p>}
      {(view === "all" || view === "active" || view === "waiting") && !!active.length && (
        <div className="space-y-8">
          {(view === "all" || view === "active") && !!open.length && (
            <section aria-labelledby="open-positions-heading">
              <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
                <div>
                  <h2 id="open-positions-heading" className="text-lg font-semibold text-white">Open positions</h2>
                  <p className="mt-1 text-sm text-slate-500">Entered trades currently being managed against their published stops and targets.</p>
                </div>
                <span className="rounded-full bg-emerald-950/70 px-2.5 py-1 text-xs font-semibold text-emerald-300">{open.length} open</span>
              </div>
              <div className="space-y-4">{open.map((signal) => <TradeCard key={signal.id} signal={signal} onUpgrade={onUpgrade} token={token} />)}</div>
            </section>
          )}

          {(view === "all" || view === "waiting") && !!pending.length && (
            <section aria-labelledby="pending-entries-heading">
              <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
                <div>
                  <h2 id="pending-entries-heading" className="text-lg font-semibold text-white">Pending entries</h2>
                  <p className="mt-1 text-sm text-slate-500">Published plans waiting for their entry conditions—these are not open positions yet.</p>
                </div>
                <span className="rounded-full bg-indigo-950/70 px-2.5 py-1 text-xs font-semibold text-indigo-300">{pending.length} pending</span>
              </div>
              <div className="space-y-4">{pending.map((signal) => <TradeCard key={signal.id} signal={signal} onUpgrade={onUpgrade} token={token} />)}</div>
            </section>
          )}
        </div>
      )}
      {(view === "all" || view === "completed") && !!history.length && (
        <section className={view === "all" && active.length ? "mt-10" : ""} aria-labelledby="completed-history-heading">
          <div className="mb-3">
            <h2 id="completed-history-heading" className="text-lg font-semibold text-white">Completed history <span className="ml-1 text-sm font-normal text-slate-500">{history.length}</span></h2>
            <p className="mt-1 text-sm text-slate-500">Closed, cancelled, expired, and unfilled setups remain visible, including losses.</p>
          </div>
          <div className="space-y-4">{history.map((signal) => <TradeCard key={signal.id} signal={signal} archived />)}</div>
        </section>
      )}

      <p className="mt-8 border-t border-slate-800 pt-5 text-xs leading-5 text-slate-500">For research and educational use only. Options can lose their entire value. Published performance does not include commissions, slippage, taxes, or differences in execution unless a record specifically says otherwise.</p>
    </div>
  );
}
