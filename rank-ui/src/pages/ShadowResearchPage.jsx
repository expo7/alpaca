import { useEffect, useState } from "react";

const label = (value) => String(value || "unknown").replaceAll("_", " ");
const time = (value) => value ? new Date(value).toLocaleString() : "Not recorded";
const pct = (value) => value == null ? "—" : `${Number(value).toFixed(2)}%`;
const text = (value) => Array.isArray(value) ? value.join(" · ") : typeof value === "object" && value !== null ? JSON.stringify(value) : String(value ?? "—");
const box = "rounded-2xl border border-slate-800 bg-slate-900/60 p-5";

function Metric({ title, value, children }) {
  return <div className={box}><p className="text-sm text-slate-400">{title}</p><p className="mt-2 text-2xl font-semibold text-white">{value}</p><p className="mt-2 text-xs text-slate-400">{children}</p></div>;
}
function Performance({ title, data }) {
  return <section className={box}><h2 className="font-semibold text-white">{title}</h2><p className="mt-1 text-sm text-slate-400">{data?.sample_size || 0} completed results · {(data?.sample_size || 0) < 30 ? "Too few results for a dependable conclusion" : "Selected research cohort"}</p><dl className="mt-5 grid grid-cols-3 gap-3 text-sm"><div><dt className="text-slate-400">Win rate</dt><dd className="mt-1 text-lg text-white">{pct(data?.win_rate_pct)}</dd></div><div><dt className="text-slate-400">Mean return</dt><dd className="mt-1 text-lg text-white">{pct(data?.expectancy_pct)}</dd></div><div><dt className="text-slate-400">Max drawdown</dt><dd className="mt-1 text-lg text-white">{pct(data?.max_drawdown_pct)}</dd></div></dl></section>;
}
function Setup({ setup }) {
  const d = setup.decision || {};
  const result = setup.result || {};
  return <article className={box}>
    <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs text-slate-400">#{setup.id} · {label(setup.category)} · {time(setup.decided_at)}</p><h3 className="mt-1 text-lg font-semibold text-white">{d.symbol} {label(d.direction)} <span className="text-sm font-normal text-slate-400">{d.option_symbol}</span></h3></div><div className="flex flex-wrap gap-2 text-xs"><span className="rounded-full bg-cyan-950 px-3 py-1 text-cyan-200">{setup.execution_mode === "observation" ? "Modeled observation" : "Broker paper setup"}</span><span className="rounded-full bg-slate-800 px-3 py-1 text-slate-200">{label(setup.status)}</span></div></div>
    <p className="mt-4 text-sm text-slate-200">{d.thesis}</p>
    <p className="mt-2 text-sm text-amber-200">{setup.rejection_reason ? `Publication gate: ${label(setup.rejection_reason)}` : d.benchmark_rationale || "Index benchmark"}</p>
    <dl className="mt-4 grid grid-cols-2 gap-4 text-sm sm:grid-cols-4"><div><dt className="text-slate-400">Entry plan</dt><dd>${d.entry_low}–${d.entry_high}</dd></div><div><dt className="text-slate-400">Stop / target 1</dt><dd>${d.stop} / ${d.target_1}</dd></div><div><dt className="text-slate-400">Realized return</dt><dd className="font-semibold">{pct(result.realized_return_pct)}</dd></div><div><dt className="text-slate-400">Sampled MFE / MAE</dt><dd>{pct(result.mfe_pct)} / {pct(result.mae_pct)}</dd></div></dl>
    {setup.has_error && <p role="status" className="mt-3 text-sm text-amber-200">A setup error is recorded. Check server diagnostics before relying on this result.</p>}
    <details className="mt-5 border-t border-slate-800 pt-4"><summary className="cursor-pointer text-sm text-cyan-200">Original decision and recorded outcome</summary><dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">{Object.entries(d).map(([key, value]) => <div key={key} className="min-w-0"><dt className="text-xs capitalize text-slate-400">{label(key)}</dt><dd className="mt-1 break-words text-slate-200">{text(value)}</dd></div>)}</dl><h4 className="mt-5 font-semibold">Recorded outcome</h4><dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2">{Object.entries(result).map(([key, value]) => <div key={key}><dt className="text-xs capitalize text-slate-400">{label(key)}</dt><dd className="break-words">{text(value)}</dd></div>)}</dl><p className="mt-3 text-xs text-slate-400">Entered {time(setup.entered_at)} · Exited {time(setup.exited_at)} · Broker reconciliation {time(setup.reconciled_at)} · Protection {label(setup.protection_kind)}</p></details>
    <details className="mt-4 border-t border-slate-800 pt-4"><summary className="cursor-pointer text-sm text-cyan-200">Event history · {setup.event_count || 0}</summary>{setup.event_count > 100 && <p className="mt-3 text-xs text-slate-400">Showing the latest 100 events. Earlier events remain in the audit record.</p>}<ol className="mt-4 space-y-4">{(setup.events || []).map((event, index) => <li key={`${event.occurred_at}-${index}`} className="border-l-2 border-cyan-900 pl-4 text-sm"><p className="font-medium capitalize">{label(event.kind)} <span className="font-normal text-slate-400">· {time(event.occurred_at)}</span></p><dl className="mt-2 space-y-1">{Object.entries(event.details || {}).map(([key, value]) => <div key={key} className="break-words"><dt className="inline text-slate-400">{label(key)}: </dt><dd className="inline">{text(value)}</dd></div>)}</dl></li>)}</ol>{!setup.events?.length && <p className="mt-3 text-sm text-slate-400">No recorded events.</p>}</details>
  </article>;
}

export default function ShadowResearchPage({ token, isStaff }) {
  const [data, setData] = useState(null);
  const [account, setAccount] = useState(null);
  const [mode, setMode] = useState("all");
  const [status, setStatus] = useState("all");
  const [page, setPage] = useState(1);
  const [refresh, setRefresh] = useState(0);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    if (!token || !isStaff) return;
    const controller = new AbortController();
    setLoading(true); setError(""); setData(null);
    fetch(`/api/staff/shadow-research/?mode=${mode}&status=${status}&page=${page}`, { headers: { Authorization: `Bearer ${token}` }, signal: controller.signal })
      .then(async r => { const json = await r.json(); if (!r.ok) throw new Error(json.detail || "Unable to load shadow research"); return json; })
      .then(setData).catch(e => { if (e.name !== "AbortError") setError(e.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [token, isStaff, mode, status, page, refresh]);
  useEffect(() => {
    if (!token || !isStaff) return;
    const controller = new AbortController();
    setAccount(null);
    fetch("/api/staff/shadow-research/account/", { headers: { Authorization: `Bearer ${token}` }, signal: controller.signal })
      .then(async r => { if (!r.ok) throw new Error(); return r.json(); })
      .then(setAccount).catch(e => { if (e.name !== "AbortError") setAccount({ status: "unavailable" }); });
    return () => controller.abort();
  }, [token, isStaff, refresh]);
  if (!isStaff || !token) return <div className="mx-auto max-w-3xl p-6"><section className={box}><h1 className="text-xl font-semibold">Shadow research is private</h1><p className="mt-2 text-slate-400">Sign in with a staff account to view this report.</p></section></div>;
  const summary = data?.summary || {};
  const modes = summary.groups?.execution_mode || {};
  return <div className="mx-auto max-w-7xl space-y-6 p-4 text-slate-200 sm:p-6">
    <header className="flex flex-wrap items-end justify-between gap-4"><div><p className="text-xs font-semibold uppercase tracking-widest text-cyan-300">Staff research lab · paper only</p><h1 className="mt-2 text-3xl font-semibold text-white">Shadow research</h1><p className="mt-2 max-w-2xl text-sm text-slate-400">Follow the ideas we recorded before their outcomes were known. Compare rejected setups and index benchmarks with the original reasoning intact.</p></div><button type="button" disabled={loading} onClick={() => setRefresh(r => r + 1)} className="rounded-xl border border-cyan-800 bg-cyan-950 px-4 py-2 text-sm text-cyan-100 disabled:opacity-50">Refresh report</button></header>
    {error && <p role="alert" className="rounded-xl border border-red-900 bg-red-950/40 p-4">{error}</p>}
    {loading && <p role="status" className="text-sm text-slate-400">Loading research records…</p>}
    <section aria-label="System health" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <Metric title="Broker execution" value={data ? summary.execution_switch_enabled ? "Enabled" : "Paused / disabled" : "Unknown"}>Executor: {label(summary.executor_health?.status)} · checked {time(summary.executor_health?.checked_at)}</Metric>
      <Metric title="Shadow paper inventory" value={!account ? "Checking…" : account.status !== "verified" ? "Unknown" : account.flat ? "Flat" : `${account.position_count} positions`}>{account?.status === "verified" ? `Account …${account.account_suffix} · ${account.open_order_count} open orders` : "Read-only verification of a distinct paper account"}</Metric>
      <Metric title="Latest recorded observation" value={summary.last_observation_at ? time(summary.last_observation_at) : "No observations"}>A recorded quote timestamp, not a sampler heartbeat.</Metric>
      <Metric title="Recorded setups" value={data ? summary.count : "—"}>{summary.near_miss || 0} near misses · {summary.index_benchmark || 0} index benchmarks</Metric>
    </section>
    {summary.executor_health?.has_error && <p className="text-sm text-amber-200">The executor has a recorded error. Inspect server diagnostics before starting entries.</p>}
    {account?.status === "unavailable" && <p role="status" className="text-sm text-amber-200">Paper account verification is unavailable. Inventory has not been confirmed.</p>}
    {account?.status === "verified" && <section className={box}><h2 className="font-semibold">Paper account check</h2><p className="mt-1 text-xs text-slate-400">Checked {time(account.checked_at)} · cached for up to 30 seconds</p><div className="mt-3 flex flex-wrap gap-3 text-sm">{account.positions.map(p => <p key={p.symbol}>{p.symbol} · {p.qty} {p.side}</p>)}{account.orders.map((o, i) => <p key={i}>{o.symbol} · {o.qty} {o.side} · {label(o.status)}</p>)}{account.flat && <p>No positions or open orders.</p>}</div></section>}
    <div className="grid gap-4 md:grid-cols-2"><Performance title="Modeled observations" data={modes.observation} /><Performance title="Broker paper executions" data={modes.broker_intended} /></div>
    <p className="text-xs leading-relaxed text-slate-400">Gross returns exclude fees. Modeled results use sampled ask/bid quotes and can miss movement between samples. Published trades in the same decision window are an unmatched comparison; this does not establish that a filter caused better or worse results.</p>
    <section className={box}><h2 className="font-semibold">Publication gates and outcomes</h2><div className="mt-4 overflow-x-auto"><table className="w-full text-left text-sm"><thead className="text-slate-400"><tr><th className="pb-3 pr-4">Gate</th><th className="pb-3 pr-4">Mode</th><th className="pb-3 pr-4">Completed</th><th className="pb-3 pr-4">Mean return</th><th className="pb-3">Win rate</th></tr></thead><tbody>{(summary.rejection_results || []).map(row => <tr key={`${row.mode}-${row.reason}`} className="border-t border-slate-800"><td className="py-3 pr-4 capitalize">{label(row.reason)}</td><td className="pr-4">{row.mode === "observation" ? "Modeled" : "Broker paper"}</td><td>{row.sample_size}</td><td>{pct(row.expectancy_pct)}</td><td>{pct(row.win_rate_pct)}</td></tr>)}</tbody></table>{!summary.rejection_results?.length && <p className="py-4 text-slate-400">No completed results to compare yet.</p>}</div><p className="mt-3 text-xs text-slate-400">Results stay separate by mode. Small samples describe these setups and do not establish a reliable trading edge.</p></section>
    <section className="space-y-4"><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-xl font-semibold">Setup journal</h2><div className="flex flex-wrap gap-2"><label className="text-sm">Mode <select aria-label="Result mode" className="ml-2 rounded-lg border border-slate-700 bg-slate-900 p-2" value={mode} onChange={e => { setMode(e.target.value); setPage(1); }}><option value="all">All</option><option value="observation">Modeled observations</option><option value="broker_intended">Broker paper setups</option></select></label><label className="text-sm">Status <select aria-label="Setup status" className="ml-2 rounded-lg border border-slate-700 bg-slate-900 p-2" value={status} onChange={e => { setStatus(e.target.value); setPage(1); }}>{["all", "proposed", "waiting", "active", "completed", "expired_unfilled", "cancelled", "rejected", "failed"].map(s => <option key={s} value={s}>{label(s)}</option>)}</select></label></div></div>
      {!loading && data && !data.results?.length && <div className={`${box} py-12 text-center`}><h3 className="font-semibold">{summary.count ? "No setups match these filters" : "Waiting for the first prospective setup"}</h3><p className="mx-auto mt-2 max-w-lg text-sm text-slate-400">{summary.count ? "Try another status or result mode." : "The research workflow records a proposal only when its exact contract, fresh quote, original decision, and levels are available. No fills or returns have been recorded yet."}</p></div>}
      {(data?.results || []).map(s => <Setup key={s.id} setup={s} />)}
      {data && (page > 1 || data.next_page) && <div className="flex items-center justify-between"><button disabled={page === 1} onClick={() => setPage(p => p - 1)} className="rounded-lg border border-slate-700 px-4 py-2 disabled:opacity-40">Previous</button><span className="text-sm text-slate-400">Page {page} · {data.count} matching setups</span><button disabled={!data.next_page} onClick={() => setPage(data.next_page)} className="rounded-lg border border-slate-700 px-4 py-2 disabled:opacity-40">Next</button></div>}
    </section><p className="text-xs text-slate-500">Report generated {time(data?.generated_at)} · Refresh to retrieve the latest recorded state.</p>
  </div>;
}
