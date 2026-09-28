import { useEffect, useState } from "react";

const SAMPLE_ACCOUNT = "c30850d2-4645-4096-be1e-4953c4a64756";

export default function BrokerSandboxPanel({ token }) {
  const [state, setState] = useState(null);
  const [accountId, setAccountId] = useState(SAMPLE_ACCOUNT);
  const [detail, setDetail] = useState(null);
  const [mirror, setMirror] = useState(null);
  const [newAccount, setNewAccount] = useState(null);
  const [funding, setFunding] = useState(null);
  const [demoOptions, setDemoOptions] = useState(false);
  const [error, setError] = useState("");
  const [symbol, setSymbol] = useState("AAPL");
  const [limitPrice, setLimitPrice] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [busy, setBusy] = useState(false);
  const headers = { Authorization: `Bearer ${token}` };

  useEffect(() => {
    if (!token) return;
    fetch("/api/broker-sandbox/", { headers })
      .then((response) => response.ok ? response.json() : null)
      .then(setState).catch(() => {});
  }, [token]);

  async function inspect() {
    setBusy(true); setError("");
    try {
      const response = await fetch(`/api/broker-sandbox/accounts/${encodeURIComponent(accountId.trim())}/`, { headers });
      if (!response.ok) throw new Error("Could not read this sandbox account.");
      setDetail(await response.json());
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  async function previewMirror() {
    setBusy(true); setError("");
    try {
      const response = await fetch(`/api/broker-sandbox/accounts/${encodeURIComponent(accountId.trim())}/mirror-preview/`, { headers });
      if (!response.ok) throw new Error("Could not inspect mirror readiness.");
      setMirror(await response.json());
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  async function inspectFunding() {
    setBusy(true); setError("");
    try {
      const response = await fetch(`/api/broker-sandbox/accounts/${encodeURIComponent(accountId.trim())}/funding/`, { headers });
      if (!response.ok) throw new Error("Could not read sandbox funding status.");
      setFunding(await response.json());
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  async function advanceFunding() {
    if (!window.confirm("Create a virtual bank link or request one $1,000 deposit for this fictional Alpaca sandbox account?")) return;
    setBusy(true); setError("");
    try {
      const response = await fetch(`/api/broker-sandbox/accounts/${encodeURIComponent(accountId.trim())}/funding/`, {
        method: "POST", headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ confirm: "FUND SYNTHETIC SANDBOX ACCOUNT" }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Funding outcome unknown; inspect before retrying.");
      setError(result.detail);
      const refreshed = await fetch(`/api/broker-sandbox/accounts/${encodeURIComponent(accountId.trim())}/funding/`, { headers });
      if (refreshed.ok) setFunding(await refreshed.json());
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  async function createSyntheticAccount() {
    if (!window.confirm(`Create one fictional ${demoOptions ? "equity + options" : "equity"} account in Alpaca Broker sandbox?`)) return;
    setBusy(true); setError(""); setNewAccount(null);
    try {
      const response = await fetch("/api/broker-sandbox/accounts/create/", {
        method: "POST", headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ options: demoOptions, confirm: "CREATE SYNTHETIC SANDBOX ACCOUNT" }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(`${result.detail || "Account outcome unknown; inspect Alpaca before retrying."}${result.validation_fields?.length ? ` Validation fields: ${result.validation_fields.join(", ")}.` : ""}`);
      setNewAccount(result); setAccountId(result.id); setDetail(null); setMirror(null); setFunding(null);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  async function submit() {
    const name = symbol.trim().toUpperCase();
    if (confirmation !== `SANDBOX BUY 1 ${name}`) { setError("Type the exact confirmation shown below."); return; }
    setBusy(true); setError("");
    try {
      const response = await fetch(`/api/broker-sandbox/accounts/${encodeURIComponent(accountId.trim())}/orders/`, {
        method: "POST", headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ symbol: name, qty: "1", limit_price: limitPrice, confirm: confirmation }),
      });
      if (!response.ok) throw new Error((await response.json()).detail || "Order outcome unknown. Check Alpaca before retrying.");
      const order = await response.json();
      setConfirmation("");
      setLimitPrice("");
      setError(`Sandbox order ${order.status}; ID ${order.id}. Refresh account to inspect it.`);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  async function cancel(order) {
    if (!window.confirm(`Cancel sandbox ${order.symbol} ${order.side} order ${order.id}?`)) return;
    setBusy(true); setError("");
    try {
      const response = await fetch(`/api/broker-sandbox/accounts/${encodeURIComponent(accountId.trim())}/orders/${encodeURIComponent(order.id)}/cancel/`, {
        method: "POST", headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ confirm: "CANCEL SANDBOX ORDER" }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Cancellation outcome unknown. Inspect the order before retrying.");
      setError(result.detail);
      const refreshed = await fetch(`/api/broker-sandbox/accounts/${encodeURIComponent(accountId.trim())}/`, { headers });
      if (refreshed.ok) setDetail(await refreshed.json());
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  if (!state) return null;
  return <aside className="mb-6 rounded-2xl border border-amber-500/35 bg-slate-900/80 p-5 text-sm text-slate-200">
    <h2 className="text-lg font-bold text-white">Broker sandbox · staff only</h2>
    <p className="mt-1 text-slate-300">Quantelle-first account infrastructure in simulation. Separate from Quantelle's house and shadow paper accounts. No live-money access.</p>
    <p className="mt-2">Server credentials: {state.configured ? "configured" : "not configured"} · Manual trial orders: {state.orders_enabled ? "enabled" : "disabled"}</p>
    <div className="mt-3 rounded-lg border border-violet-500/40 p-3">
      <p className="font-semibold">Open a fictional Broker sandbox account</p>
      <p>Admin demonstration only. Alpaca will receive generated test identity and simulated agreement data. No real applicant or money.</p>
      <label className="mt-2 flex items-center gap-2"><input type="checkbox" checked={demoOptions} onChange={(e) => setDemoOptions(e.target.checked)} />Request US options asset too (requires Alpaca partner enablement)</label>
      <button type="button" disabled={busy || !state.configured} onClick={createSyntheticAccount} className="mt-2 rounded-lg border border-violet-400 px-4 py-2 font-semibold text-violet-200 disabled:opacity-50">Create synthetic sandbox account</button>
      {newAccount && <p role="status" className="mt-2">Created account {newAccount.id} · {newAccount.account_number} · {newAccount.status}. Its ID is selected below; inspect it for updates.</p>}
    </div>
    <div className="mt-3 flex flex-wrap gap-2">
      <input aria-label="Sandbox account ID" value={accountId} onChange={(e) => { setAccountId(e.target.value); setDetail(null); setMirror(null); setFunding(null); }} className="min-w-72 flex-1 rounded-lg bg-slate-800 p-2" />
      <button type="button" disabled={busy || !state.configured} onClick={inspect} className="rounded-lg bg-amber-400 px-4 py-2 font-semibold text-slate-950 disabled:opacity-50">Inspect account</button>
      <button type="button" disabled={busy || !state.configured} onClick={previewMirror} className="rounded-lg border border-sky-400 px-4 py-2 font-semibold text-sky-200 disabled:opacity-50">Preview options mirror</button>
    </div>
    {detail?.account.status === "ACTIVE" && <div className="mt-3 rounded-lg border border-emerald-500/40 p-3">
      <p className="font-semibold">Virtual sandbox funding</p>
      <p>Create a fictional ACH link, wait for approval, then request one $1,000 sandbox deposit. No real bank or money.</p>
      <div className="mt-2 flex gap-2">
        <button type="button" disabled={busy} onClick={inspectFunding} className="rounded border border-emerald-400 px-3 py-2 disabled:opacity-50">Inspect funding</button>
        <button type="button" disabled={busy} onClick={advanceFunding} className="rounded border border-emerald-400 px-3 py-2 disabled:opacity-50">Next funding step</button>
      </div>
      {funding && <p className="mt-2">Bank links: {funding.relationships.map((item) => item.status).join(", ") || "none"} · Deposits: {funding.transfers.filter((item) => item.direction === "INCOMING").map((item) => `$${item.amount} ${item.status}`).join(", ") || "none"}</p>}
    </div>}
    {mirror && <div className="mt-3 rounded-lg border border-sky-500/40 p-3">
      <p className="font-semibold">Live Options → Broker sandbox · read-only preview</p>
      {mirror.signal ? <>
        <p>Published setup #{mirror.signal.id}: {mirror.signal.contract} · {mirror.signal.status} · house paper order {mirror.signal.paper_order_status || "none"}</p>
        <p>One contract estimate: ${mirror.signal.one_contract_estimate} · Broker orders: disabled for mirroring</p>
        <p>Account: {mirror.account.enabled_assets.join(", ") || "none"} · options level {mirror.account.options_trading_level}/{mirror.account.options_approved_level} · options buying power {mirror.account.options_buying_power ?? "unavailable"}</p>
        <ul className="mt-2 list-inside list-disc">{Object.entries(mirror.checks).map(([key, ok]) => <li key={key}>{key.replaceAll("_", " ")}: {ok ? "ready" : "blocked"}</li>)}</ul>
      </> : <p>{mirror.detail}</p>}
    </div>}
    {detail && <div className="mt-3">
      <p>Status: {detail.account.status || "unknown"} · Assets: {detail.account.enabled_assets.join(", ") || "pending"} · Cash: {detail.account.cash == null ? "unavailable" : `$${detail.account.cash}`} · Buying power: {detail.account.buying_power == null ? "unavailable" : `$${detail.account.buying_power}`}</p>
      {detail.account.status !== "ACTIVE" && <p role="status" className="mt-2 text-amber-200">Alpaca has the application. Inspect again later for ACTIVE status before testing orders.</p>}
      <p>Recent orders: {detail.orders.length ? "" : "none"}</p>
      {detail.orders.map((order) => <div key={order.id} className="mt-2 rounded-lg border border-slate-700 p-2">
        <span>{order.symbol} {order.side} {order.qty} · {order.status} · limit ${order.limit_price || "—"} · filled {order.filled_qty || "0"}{order.filled_avg_price ? ` at $${order.filled_avg_price}` : ""}</span>
        {state.orders_enabled && order.client_order_id?.startsWith("quantelle-admin-sandbox-") && ["accepted", "new", "pending_new", "partially_filled", "held", "done_for_day"].includes(order.status) &&
          <button type="button" disabled={busy} onClick={() => cancel(order)} className="ml-3 rounded border border-amber-400 px-2 py-1 text-amber-200 disabled:opacity-50">Cancel order</button>}
      </div>)}
      {state.orders_enabled && detail.account.status === "ACTIVE" && <div className="mt-4 space-y-2 border-t border-slate-700 pt-3">
        <p>Manual sandbox trial: one US equity share, day limit buy. Check price and buying power before submitting.</p>
        <div className="flex flex-wrap gap-2">
          <input aria-label="Symbol" value={symbol} onChange={(e) => setSymbol(e.target.value)} className="w-28 rounded-lg bg-slate-800 p-2" />
          <input aria-label="Limit price" value={limitPrice} onChange={(e) => setLimitPrice(e.target.value)} placeholder="Limit price" className="w-32 rounded-lg bg-slate-800 p-2" />
          <input aria-label="Confirmation" value={confirmation} onChange={(e) => setConfirmation(e.target.value)} placeholder={`SANDBOX BUY 1 ${symbol.trim().toUpperCase()}`} className="min-w-52 rounded-lg bg-slate-800 p-2" />
          <button type="button" disabled={busy} onClick={submit} className="rounded-lg border border-amber-400 px-4 py-2 font-semibold text-amber-200 disabled:opacity-50">Submit sandbox order</button>
        </div>
      </div>}
    </div>}
    {error && <p role="status" className="mt-3 text-amber-200">{error}</p>}
  </aside>;
}
