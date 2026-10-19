import { useEffect, useState } from "react";

const base = "/api/alpaca-paper/";
const button = "rounded-lg border border-indigo-400/60 px-3 py-2 text-sm font-semibold text-indigo-100 hover:bg-indigo-900 disabled:opacity-40";
const input = "mt-1 w-full rounded-lg border border-slate-600 bg-slate-950 p-2 text-sm text-white";
const format = value => value == null ? "Unknown" : `$${Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;

export default function CustomerPaperPanel({ token, signals = [] }) {
  const [connection, setConnection] = useState(null);
  const [account, setAccount] = useState(null);
  const [ledger, setLedger] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [secret, setSecret] = useState("");
  const [budget, setBudget] = useState("1000");
  const [positions, setPositions] = useState("2");
  const [consent, setConsent] = useState(false);
  const [signalId, setSignalId] = useState("");
  const [plan, setPlan] = useState(null);

  async function api(path, method = "GET", body) {
    const result = await fetch(base + path, { method, headers: { Authorization: `Bearer ${token}`, ...(body ? { "Content-Type": "application/json" } : {}) }, ...(body ? { body: JSON.stringify(body) } : {}) });
    const data = result.status === 204 ? null : await result.json();
    if (!result.ok) throw new Error(data?.detail || "Paper account request failed.");
    return data;
  }

  useEffect(() => {
    if (!token) return;
    let active = true;
    fetch(base + "connection/", { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.ok ? r.json() : null).then(data => {
        if (active) { setConnection(data); if (data) { setBudget(data.max_trade_notional || "1000"); setPositions(String(data.max_open_positions || 2)); } }
      }).catch(() => { if (active) setError("Could not load the paper connection."); });
    return () => { active = false; };
  }, [token]);

  async function action(work) {
    setBusy(true); setError("");
    try { await work(); } catch (err) { setError(err.message); } finally { setBusy(false); }
  }

  async function refresh() {
    setAccount(null); // Failed broker reads must show unknown, not an old balance.
    const history = await api("executions/"); setLedger(history);
    const state = await api("connection/"); setConnection(state);
    const details = await api("account/"); setAccount(details);
  }

  async function connect(e) {
    e.preventDefault();
    const key = apiKey, value = secret;
    setApiKey(""); setSecret("");
    await action(async () => { const state = await api("connection/", "POST", { api_key: key, api_secret: value }); setConnection(state); setConsent(false); setPlan(null); await refresh(); });
  }

  async function settings(mirrorEnabled) {
    await action(async () => {
      const state = await api("connection/", "PATCH", { max_trade_notional: budget, max_open_positions: Number(positions), ...(mirrorEnabled == null ? {} : { mirror_enabled: mirrorEnabled, consent }) });
      setConnection(state); setConsent(false); setPlan(null);
    });
  }

  if (!connection) return error ? <p role="alert" className="mb-4 text-rose-300">{error}</p> : null;
  const eligible = signals.filter(s => ["published", "open"].includes(s.status) && ["call", "put"].includes(s.instrument_type));
  return <aside className="mb-6 space-y-4 rounded-2xl border border-indigo-500/40 bg-indigo-950/25 p-5">
    <div><h2 className="text-lg font-bold text-white">Connect your Alpaca paper account</h2>
      <p className="mt-1 text-sm text-slate-300">{connection.customer_rollout ? "Paper trading" : "Admin preview"} · Use a separate paper account to follow Quantelle trades. Each entry buys one options contract within your limits.</p></div>
    <ol className="grid gap-2 text-sm text-slate-300 sm:grid-cols-3"><li>1. Connect paper credentials</li><li>2. Inspect funds and options access</li><li>3. Preview a trade or enable mirroring</li></ol>
    {!connection.available && <p role="status" className="text-amber-200">Paper credential storage is not configured on the server yet.</p>}
    {!connection.connected && connection.available && <form onSubmit={connect} autoComplete="off" className="space-y-3">
      <p className="text-sm text-slate-300">In Alpaca, switch to <strong>Paper Trading</strong> and generate an API key. Paste the key pair here. Credentials are encrypted on the server.</p>
      <div className="grid gap-3 sm:grid-cols-2"><label className="text-sm text-slate-300">Paper API key<input aria-label="Paper API key" type="password" autoComplete="off" spellCheck="false" value={apiKey} onChange={e => setApiKey(e.target.value)} className={input} required /></label>
      <label className="text-sm text-slate-300">Paper API secret<input aria-label="Paper API secret" type="password" autoComplete="new-password" spellCheck="false" value={secret} onChange={e => setSecret(e.target.value)} className={input} required /></label></div>
      <button type="submit" className={button} disabled={busy}>Verify and save paper account</button>
    </form>}
    {!connection.connected && connection.oauth_available && <button disabled={busy} className={button} onClick={() => action(async () => { const data = await api("connect/", "POST"); window.location.assign(data.authorize_url); })}>Connect through Alpaca authorization</button>}
    {connection.connected && <>
      <div className="flex flex-wrap items-center gap-3 text-sm text-white"><span>Paper account ending {connection.account_suffix}</span><span className="rounded-full border border-slate-600 px-2 py-1">Mirroring {connection.mirror_enabled ? "on" : "off"}</span>
        <button disabled={busy} className={button} onClick={() => action(refresh)}>Inspect account / refresh</button>
        <button disabled={busy || connection.mirror_enabled} className={button} onClick={() => action(async () => { await api("connection/", "DELETE"); setConnection(await api("connection/")); setAccount(null); setPlan(null); })}>Disconnect</button></div>
      {connection.executor_ready === false && <p className="text-amber-200">The customer paper worker is unavailable. New entries are paused; broker-held protection stays in place.</p>}
      {!connection.execution_enabled && <p className="text-amber-200">The server entry switch is off. Existing customer exits remain managed.</p>}
      {!connection.trading_authorized && <p className="text-amber-200">This authorization is read-only. Reconnect with paper API keys or grant trading permission.</p>}
      {account ? <section className="space-y-2 rounded-xl bg-slate-950/60 p-3 text-sm text-slate-200">
        <p>Cash {format(account.account.cash)} · Options buying power {format(account.account.options_buying_power)} · Options level {account.account.options_trading_level ?? "Unknown"} · {account.account.status}</p>
        <p>{account.positions.length} positions · {account.orders.length} open orders · Checked {new Date(account.checked_at).toLocaleString()}</p>
        {account.positions.map(p => <p key={p.symbol}>{p.symbol} · {p.qty} {p.side} · P/L {format(p.unrealized_pl)}</p>)}
        {account.orders.map(o => <p key={o.id}>{o.symbol} · {o.side} {o.qty} · {o.type} · {o.status}</p>)}
      </section> : <p className="text-sm text-slate-400">Inspect the account to retrieve its current balance, orders, and options access.</p>}
      <div className="grid gap-3 sm:grid-cols-3"><label className="text-sm text-slate-300">Maximum cost per trade ($)<input type="number" min="1" max="100000" step="0.01" value={budget} onChange={e => { setBudget(e.target.value); setPlan(null); }} className={input} /></label>
        <label className="text-sm text-slate-300">Maximum positions<input type="number" min="1" max="10" value={positions} onChange={e => { setPositions(e.target.value); setPlan(null); }} className={input} /></label>
        <button disabled={busy} className={`${button} self-end`} onClick={() => settings(null)}>Save trade limits</button></div>
      {!connection.mirror_enabled && <label className="flex gap-2 text-sm text-slate-300"><input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} />I authorize automatic paper entries for new Quantelle trades and ongoing exit management. Turning mirroring off stops new entries.</label>}
      <button className={button} disabled={busy || (!connection.mirror_enabled && (!consent || !connection.execution_enabled || connection.executor_ready === false || !connection.trading_authorized))} onClick={() => settings(!connection.mirror_enabled)}>{connection.mirror_enabled ? "Pause new mirror entries" : "Enable paper mirroring"}</button>
      <p className="text-xs text-slate-400">Mirroring starts with the next fresh house entry after you enable it. Existing and missed entries are not replayed. Disconnecting requires all Quantelle customer orders to be resolved first.</p>
      <section className="space-y-3 border-t border-slate-700 pt-4"><h3 className="font-semibold text-white">Try one published trade</h3><p className="text-sm text-slate-300">Preview one contract at the current paper quote. The market must be open and the premium must remain within the published entry range.</p>
        <select aria-label="Paper trade signal" className={input} value={signalId} onChange={e => { setSignalId(e.target.value); setPlan(null); }}><option value="">Choose a signal</option>{eligible.map(s => <option key={s.id} value={s.id}>{s.display_instrument || s.symbol} · #{s.id}</option>)}</select>
        <button className={button} disabled={busy || !signalId || !connection.execution_enabled || connection.executor_ready === false || !connection.trading_authorized} onClick={() => action(async () => { setPlan(null); setPlan(await api("executions/", "POST", { signal_id: Number(signalId), action: "preview" })); })}>Preview one-contract paper trade</button>
        {plan && <div className="space-y-3 rounded-lg bg-slate-950 p-3 text-sm text-slate-200"><p>{plan.symbol} · Buy 1 · Limit {format(plan.limit_price)} · Estimated cost {format(plan.estimated_cost)} · Stop {format(plan.stop)} · Target {format(plan.target)}</p><button className={button} disabled={busy} onClick={() => action(async () => { setPlan(null); await api("executions/", "POST", { signal_id: Number(signalId), action: "submit", confirm_paper: true }); await refresh(); })}>Confirm paper order</button></div>}
      </section>
      {connection.last_error && <p role="status" className="text-amber-200">{connection.last_error}</p>}
      {ledger && <section className="space-y-2 border-t border-slate-700 pt-3"><h3 className="font-semibold text-white">Your customer execution history</h3>{!ledger.executions.length && <p className="text-sm text-slate-400">No customer trades yet.</p>}{ledger.executions.map(row => <div key={row.id} className="rounded-lg bg-slate-950/60 p-3 text-sm text-slate-200"><p>{row.symbol} · {row.source} · {row.state.replaceAll("_", " ")} · {row.order_status}</p><p>Entry {format(row.entry_fill)} · Exit {format(row.exit_fill)}</p>{row.last_error && <p className="text-amber-200">{row.last_error}</p>}</div>)}<details className="text-xs text-slate-400"><summary>Recent connection and order events</summary>{ledger.events.map((e, i) => <p key={i}>{new Date(e.created_at).toLocaleString()} · {e.kind.replaceAll("_", " ")}</p>)}</details></section>}
    </>}
    {error && <p role="alert" className="text-sm text-rose-300">{error}</p>}
  </aside>;
}
