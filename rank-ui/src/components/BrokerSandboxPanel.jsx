import { useEffect, useState } from "react";

const SAMPLE_ACCOUNT = "c30850d2-4645-4096-be1e-4953c4a64756";

export default function BrokerSandboxPanel({ token }) {
  const [state, setState] = useState(null);
  const [accountId, setAccountId] = useState(SAMPLE_ACCOUNT);
  const [detail, setDetail] = useState(null);
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
      setError(`Sandbox order ${order.status}; ID ${order.id}. Refresh account to inspect it.`);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  if (!state) return null;
  return <aside className="mb-6 rounded-2xl border border-amber-500/35 bg-slate-900/80 p-5 text-sm text-slate-200">
    <h2 className="text-lg font-bold text-white">Broker sandbox · staff only</h2>
    <p className="mt-1 text-slate-300">Quantelle-first account infrastructure in simulation. Separate from Quantelle's house and shadow paper accounts. No live-money access.</p>
    <p className="mt-2">Server credentials: {state.configured ? "configured" : "not configured"} · Manual trial orders: {state.orders_enabled ? "enabled" : "disabled"}</p>
    <div className="mt-3 flex flex-wrap gap-2">
      <input aria-label="Sandbox account ID" value={accountId} onChange={(e) => setAccountId(e.target.value)} className="min-w-72 flex-1 rounded-lg bg-slate-800 p-2" />
      <button type="button" disabled={busy || !state.configured} onClick={inspect} className="rounded-lg bg-amber-400 px-4 py-2 font-semibold text-slate-950 disabled:opacity-50">Inspect account</button>
    </div>
    {detail && <div className="mt-3">
      <p>Status: {detail.account.status} · Cash: ${detail.account.cash} · Buying power: ${detail.account.buying_power}</p>
      <p>Recent orders: {detail.orders.length ? detail.orders.map((order) => `${order.symbol} ${order.side} ${order.qty} (${order.status})`).join("; ") : "none"}</p>
      {state.orders_enabled && <div className="mt-4 space-y-2 border-t border-slate-700 pt-3">
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
