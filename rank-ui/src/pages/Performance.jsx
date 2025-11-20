import { useEffect, useMemo, useState } from "react";
import { useAuth } from "../AuthProvider.jsx";

const BASE = "http://127.0.0.1:8000";

async function apiFetch(path, { token, ...opts } = {}) {
  const headers = { ...(opts.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${BASE}${path}`, { ...opts, headers });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data?.detail || JSON.stringify(data));
  }
  return data;
}

export default function Performance() {
  const { token } = useAuth();
  const [portfolios, setPortfolios] = useState([]);
  const [selectedId, setSelectedId] = useState("");
  const [metrics, setMetrics] = useState(null);
  const [snapshots, setSnapshots] = useState([]);
  const [movements, setMovements] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [cashMsg, setCashMsg] = useState("");
  const [cashError, setCashError] = useState("");
  const [cashDraft, setCashDraft] = useState({ amount: "", reason: "" });

  useEffect(() => {
    if (!token) return;
    (async () => {
      try {
        const list = await apiFetch("/api/paper/portfolios/", { token });
        setPortfolios(list);
        if (list.length && !selectedId) {
          setSelectedId(String(list[0].id));
        }
      } catch (err) {
        console.error(err);
        setError("Failed to load portfolios");
      }
    })();
  }, [token]);

  useEffect(() => {
    if (!token || !selectedId) return;
    setLoading(true);
    setError("");
    (async () => {
      try {
        const perf = await apiFetch(
          `/api/paper/portfolios/${selectedId}/performance/`,
          { token }
        );
        setMetrics(perf);
        const snaps = await apiFetch(
          `/api/paper/portfolios/${selectedId}/performance/snapshots/?limit=45`,
          { token }
        );
        setSnapshots(snaps);
        const mvts = await apiFetch(
          `/api/paper/portfolios/${selectedId}/cash-movements/?limit=50`,
          { token }
        );
        setMovements(mvts);
      } catch (err) {
        console.error(err);
        setError("Failed to load performance data");
      } finally {
        setLoading(false);
      }
    })();
  }, [token, selectedId]);

  const sparkPoints = useMemo(() => {
    if (!snapshots.length) return "";
    const values = snapshots.map((s) => Number(s.equity));
    const min = Math.min(...values);
    const max = Math.max(...values);
    return values
      .map((value, idx) => {
        const x =
          values.length === 1 ? 0 : (idx / (values.length - 1)) * 100;
        const normalized =
          max === min ? 0.5 : (value - min) / (max - min);
        const y = 100 - normalized * 80 - 10;
        return `${x},${y}`;
      })
      .join(" ");
  }, [snapshots]);

  if (!token) {
    return (
      <div className="p-4 text-sm text-amber-300">
        Login required to view portfolio performance.
      </div>
    );
  }

  const handleCashMove = async (movement) => {
    if (!selectedId) return;
    setCashError("");
    setCashMsg("");
    if (!cashDraft.amount) {
      setCashError("Enter an amount first.");
      return;
    }
    try {
      await apiFetch(
        `/api/paper/portfolios/${selectedId}/${movement}/`,
        {
          token,
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            amount: cashDraft.amount,
            reason: cashDraft.reason,
          }),
        }
      );
      setCashMsg(`${movement} successful`);
      setCashDraft((prev) => ({ ...prev, amount: "" }));
      // refresh perf + movements
      const perf = await apiFetch(
        `/api/paper/portfolios/${selectedId}/performance/`,
        { token }
      );
      setMetrics(perf);
      const mvts = await apiFetch(
        `/api/paper/portfolios/${selectedId}/cash-movements/?limit=50`,
        { token }
      );
      setMovements(mvts);
    } catch (err) {
      setCashError(err.message || "Cash action failed");
    }
  };

  return (
    <div className="p-4 lg:p-6 space-y-4">
      <div className="flex flex-wrap items-center gap-3 justify-between">
        <div>
          <h1 className="text-lg font-semibold">Portfolio Performance</h1>
          <p className="text-sm text-slate-400">
            Track daily equity curves and returns.
          </p>
        </div>
        <select
          value={selectedId}
          onChange={(e) => setSelectedId(e.target.value)}
          className="bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-sm"
        >
          {portfolios.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
          {!portfolios.length && (
            <option value="">No portfolios</option>
          )}
        </select>
      </div>

      {error && (
        <div className="text-xs text-rose-200 bg-rose-900/30 border border-rose-800 rounded-xl px-3 py-2">
          {error}
        </div>
      )}

      <div className="grid md:grid-cols-4 gap-4">
        <MetricCard
          label="Equity"
          value={metrics ? `$${Number(metrics.equity).toFixed(2)}` : "—"}
        />
        <MetricCard
          label="Cash"
          value={metrics ? `$${Number(metrics.cash).toFixed(2)}` : "—"}
        />
        <MetricCard
          label="Total Return"
          value={
            metrics
              ? `${Number(metrics.total_return_pct).toFixed(2)}%`
              : "—"
          }
        />
        <MetricCard
          label="Realized / Unrealized"
          value={
            metrics
              ? `$${Number(metrics.realized_pnl).toFixed(
                  2
                )} / $${Number(metrics.unrealized_pnl).toFixed(2)}`
              : "—"
          }
        />
      </div>

      <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-4 space-y-3">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h2 className="text-sm font-semibold">Equity Curve</h2>
            <p className="text-xs text-slate-400">
              Last {snapshots.length} snapshots
            </p>
          </div>
          {metrics && (
            <span className="text-xs text-slate-500">
              Active {metrics.days_active} days
            </span>
          )}
        </div>
        <div className="h-40">
          {snapshots.length ? (
            <svg viewBox="0 0 100 100" className="w-full h-full">
              <polyline
                fill="none"
                stroke="url(#sparkGradient)"
                strokeWidth="2"
                points={sparkPoints}
              />
              <defs>
                <linearGradient id="sparkGradient" x1="0" x2="1" y1="0" y2="0">
                  <stop offset="0%" stopColor="#a5b4fc" />
                  <stop offset="100%" stopColor="#22d3ee" />
                </linearGradient>
              </defs>
            </svg>
          ) : (
            <div className="text-xs text-slate-500">
              {loading ? "Loading..." : "No snapshots yet."}
            </div>
          )}
        </div>
        <div className="border-t border-slate-800 pt-3 grid md:grid-cols-2 gap-3">
          <div>
            <h3 className="text-xs font-semibold text-slate-300 mb-2">
              Cash actions
            </h3>
            {cashError && (
              <div className="text-xs text-rose-200 bg-rose-900/30 border border-rose-800 rounded-xl px-3 py-2 mb-2">
                {cashError}
              </div>
            )}
            {cashMsg && (
              <div className="text-xs text-emerald-200 bg-emerald-900/20 border border-emerald-800 rounded-xl px-3 py-2 mb-2">
                {cashMsg}
              </div>
            )}
            <div className="flex flex-col gap-2">
              <input
                type="number"
                value={cashDraft.amount}
                onChange={(e) =>
                  setCashDraft((prev) => ({ ...prev, amount: e.target.value }))
                }
                placeholder="Amount"
                className="bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-sm"
              />
              <input
                type="text"
                value={cashDraft.reason}
                onChange={(e) =>
                  setCashDraft((prev) => ({ ...prev, reason: e.target.value }))
                }
                placeholder="Reason (optional)"
                className="bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-sm"
              />
              <div className="flex gap-2">
                <button
                  onClick={() => handleCashMove("deposit")}
                  className="px-3 py-2 rounded-xl bg-emerald-600 text-xs font-semibold"
                >
                  Deposit
                </button>
                <button
                  onClick={() => handleCashMove("withdraw")}
                  className="px-3 py-2 rounded-xl bg-amber-600 text-xs font-semibold"
                >
                  Withdraw
                </button>
              </div>
            </div>
          </div>
          <div>
            <h3 className="text-xs font-semibold text-slate-300 mb-2">
              Cash movements (latest)
            </h3>
            <div className="max-h-48 overflow-auto border border-slate-800 rounded-xl">
              <table className="w-full text-xs">
                <thead className="text-slate-400 bg-slate-900/60">
                  <tr>
                    <th className="px-3 py-2 text-left">Type</th>
                    <th className="px-3 py-2 text-left">Amount</th>
                    <th className="px-3 py-2 text-left">Reason</th>
                    <th className="px-3 py-2 text-left">When</th>
                  </tr>
                </thead>
                <tbody>
                  {movements.length === 0 && (
                    <tr>
                      <td
                        colSpan={4}
                        className="px-3 py-3 text-slate-500 text-center"
                      >
                        No movements yet.
                      </td>
                    </tr>
                  )}
                  {movements.map((m) => (
                    <tr key={m.id} className="border-t border-slate-800">
                      <td className="px-3 py-2 capitalize">{m.movement_type}</td>
                      <td className="px-3 py-2">
                        ${Number(m.amount).toLocaleString()}
                      </td>
                      <td className="px-3 py-2 text-slate-400">
                        {m.reason || "—"}
                      </td>
                      <td className="px-3 py-2 text-slate-500">
                        {new Date(m.created_at).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      <div className="bg-slate-900/50 border border-slate-800 rounded-2xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="text-slate-400 bg-slate-900/60 text-xs">
            <tr>
              <th className="px-3 py-2 text-left">Timestamp</th>
              <th className="px-3 py-2 text-left">Equity</th>
              <th className="px-3 py-2 text-left">Cash</th>
              <th className="px-3 py-2 text-left">Realized</th>
              <th className="px-3 py-2 text-left">Unrealized</th>
            </tr>
          </thead>
          <tbody>
            {snapshots.slice(-10).map((snap) => (
              <tr key={snap.id} className="border-t border-slate-800 text-xs">
                <td className="px-3 py-2">
                  {new Date(snap.timestamp).toLocaleString()}
                </td>
                <td className="px-3 py-2">${Number(snap.equity).toFixed(2)}</td>
                <td className="px-3 py-2">${Number(snap.cash).toFixed(2)}</td>
                <td className="px-3 py-2">
                  ${Number(snap.realized_pnl).toFixed(2)}
                </td>
                <td className="px-3 py-2">
                  ${Number(snap.unrealized_pnl).toFixed(2)}
                </td>
              </tr>
            ))}
            {!snapshots.length && (
              <tr>
                <td className="px-3 py-4 text-center text-slate-500" colSpan={5}>
                  {loading ? "Loading..." : "No data yet."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function MetricCard({ label, value }) {
  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-4">
      <div className="text-xs uppercase tracking-wide text-slate-500">
        {label}
      </div>
      <div className="text-lg font-semibold mt-1">{value}</div>
    </div>
  );
}
