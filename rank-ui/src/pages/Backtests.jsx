// ==============================
// File: src/pages/Backtests.jsx
// Top-N momentum basket backtest UI + saved configs
// ==============================

import { useEffect, useState } from "react";
import { useAuth } from "../AuthProvider.jsx";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
  ResponsiveContainer,
} from "recharts";

const BASE = "http://127.0.0.1:8000";

// Safer fetch wrapper that can handle non-JSON errors
async function apiFetch(path, token, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${BASE}${path}`, { ...options, headers });

  const text = await res.text();
  let data = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { raw: text };
  }

  if (!res.ok) {
    const msg =
      data.error ||
      data.detail ||
      data.raw ||
      `HTTP ${res.status}`;
    throw new Error(msg);
  }

  return data;
}

export default function Backtests() {

  const [strategyName, setStrategyName] = useState("");
  const [savedRuns, setSavedRuns] = useState([]);
  const [loadingRuns, setLoadingRuns] = useState(false);

  const { token } = useAuth();

  // -------- form state --------
  const [tickers, setTickers] = useState("AAPL,MSFT,NVDA,TSLA,AMD");
  const [start, setStart] = useState("2024-08-01");
  const [end, setEnd] = useState("2024-11-13");
  const [initialCap, setInitialCap] = useState(10000);
  const [rebalanceDays, setRebalanceDays] = useState(5);
  const [topN, setTopN] = useState(3);

  // saved configs
  const [configName, setConfigName] = useState("");
  const [configs, setConfigs] = useState([]);
  const [saveErr, setSaveErr] = useState("");

  // -------- result state --------
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [err, setErr] = useState("");

  if (!token) {
    return (
      <div className="text-sm text-rose-300">
        You must be logged in to run backtests.
      </div>
    );
  }

  // -------- load saved configs on mount --------
  useEffect(() => {
    if (!token) return;
    loadConfigs();
    loadRuns();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function loadConfigs() {
    try {
      setSaveErr("");
      const data = await apiFetch("/api/backtests/", token);
      setConfigs(Array.isArray(data) ? data : []);
    } catch (e) {
      setSaveErr(e.message || String(e));
    }
  }
  async function saveRun() {
    if (!result) return;
    setSaveErr("");

    try {
      const parsedTickers = tickers
        .split(",")
        .map((s) => s.trim().toUpperCase())
        .filter(Boolean);

      const payload = {
        name:
          strategyName.trim() ||
          `Run ${new Date().toLocaleString()}`,
        tickers: parsedTickers,
        start,
        end,
        benchmark: result?.benchmark?.symbol || "SPY",
        initial_capital: Number(initialCap),
        rebalance_days: Number(rebalanceDays),
        top_n: Number(topN) || null,
        summary: result?.summary || {},
      };

      await apiFetch("/api/backtest-runs/", token, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      setStrategyName("");
      await loadRuns();
    } catch (e) {
      setSaveErr(e.message || String(e));
    }
  }

  async function runBacktest(e, fromConfig) {
    if (e) e.preventDefault();
    setLoading(true);
    setErr("");
    setResult(null);

    const symbols = tickers
      .split(",")
      .map((s) => s.trim().toUpperCase())
      .filter(Boolean);

    if (!symbols.length) {
      setErr("Please enter at least one ticker.");
      setLoading(false);
      return;
    }

    try {
      const payload = {
        tickers: symbols,
        start,
        end,
        initial_capital: Number(initialCap),
        rebalance_days: Number(rebalanceDays),
        top_n: Number(topN) || null,
      };

      const data = await apiFetch("/api/backtest/", token, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      setResult(data);
    } catch (e) {
      setErr(e.message || String(e));
    } finally {
      setLoading(false);
    }
  }
  async function loadRuns() {
    if (!token) return;
    setLoadingRuns(true);
    try {
      const data = await apiFetch("/api/backtest-runs/", token);
      setSavedRuns(Array.isArray(data) ? data : []);
    } catch (e) {
      // optional: setSaveErr(e.message || String(e));
    } finally {
      setLoadingRuns(false);
    }
  }


  async function saveConfig() {
    setSaveErr("");

    const symbols = tickers
      .split(",")
      .map((s) => s.trim().toUpperCase())
      .filter(Boolean);

    if (!configName.trim()) {
      setSaveErr("Please enter a name for this backtest.");
      return;
    }
    if (!symbols.length) {
      setSaveErr("Please enter at least one ticker.");
      return;
    }

    const payload = {
      name: configName.trim(),
      tickers: symbols.join(","),
      start,
      end,
      initial_capital: Number(initialCap),
      rebalance_days: Number(rebalanceDays),
      top_n: Number(topN) || null,
      benchmark: "SPY",
    };

    try {
      await apiFetch("/api/backtests/", token, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      setConfigName("");
      await loadConfigs();
    } catch (e) {
      setSaveErr(e.message || String(e));
    }
  }

  function applyConfig(cfg) {
    setTickers(cfg.tickers);
    setStart(cfg.start);
    setEnd(cfg.end);
    setInitialCap(cfg.initial_capital);
    setRebalanceDays(cfg.rebalance_days);
    setTopN(cfg.top_n || "");
  }

  async function deleteConfig(id) {
    try {
      setSaveErr("");
      await apiFetch(`/api/backtests/${id}/`, token, {
        method: "DELETE",
      });
      setConfigs((prev) => prev.filter((c) => c.id !== id));
    } catch (e) {
      setSaveErr(e.message || String(e));
    }
  }

  // --- prepare chart data safely ---
  const equity = result?.equity_curve || [];
  const bench = result?.benchmark?.curve || [];

  const chartData = (() => {
    if (!equity.length && !bench.length) return [];
    const byDate = new Map();

    equity.forEach((pt) => {
      if (!pt || !pt.date) return;
      const d = pt.date.slice(0, 10);
      if (!byDate.has(d)) byDate.set(d, { date: d });
      byDate.get(d).portfolio = pt.value;
    });

    bench.forEach((pt) => {
      if (!pt || !pt.date) return;
      const d = pt.date.slice(0, 10);
      if (!byDate.has(d)) byDate.set(d, { date: d });
      byDate.get(d).benchmark = pt.value;
    });

    return Array.from(byDate.values()).sort((a, b) =>
      a.date.localeCompare(b.date)
    );
  })();

  const summary = result?.summary || null;
  const perTicker = result?.per_ticker || [];

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-4 flex items-center justify-between">
        <div>
          <div className="text-lg font-semibold">Backtests</div>
          <div className="text-sm text-slate-400">
            Top-N momentum basket vs benchmark with configurable rebalancing.
          </div>
        </div>
      </div>

      {/* Form + Save row */}
      <form
        onSubmit={runBacktest}
        className="bg-slate-900/50 border border-slate-800 rounded-2xl p-4 space-y-4"
      >
        <div className="grid lg:grid-cols-2 gap-4">
          {/* Tickers + dates */}
          <div className="space-y-3">
            <div>
              <label className="block text-sm mb-1">
                Tickers (comma-separated)
              </label>
              <input
                value={tickers}
                onChange={(e) => setTickers(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm"
                placeholder="AAPL, MSFT, NVDA, TSLA, AMD"
              />
            </div>

            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <label className="block text-xs text-slate-400 mb-1">
                  Start
                </label>
                <input
                  type="date"
                  value={start}
                  onChange={(e) => setStart(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">
                  End
                </label>
                <input
                  type="date"
                  value={end}
                  onChange={(e) => setEnd(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm"
                />
              </div>
            </div>
          </div>

          {/* Strategy params */}
          <div className="grid grid-cols-3 gap-3 text-sm">
            <div>
              <label className="block text-xs text-slate-400 mb-1">
                Initial capital
              </label>
              <input
                type="number"
                value={initialCap}
                onChange={(e) => setInitialCap(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm"
                min={1000}
                step={500}
              />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">
                Rebalance days
              </label>
              <input
                type="number"
                value={rebalanceDays}
                onChange={(e) => setRebalanceDays(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm"
                min={1}
                step={1}
              />
              <p className="text-[11px] text-slate-500 mt-1">
                Every N trading days, re-pick the top momentum names.
              </p>
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">
                Top N
              </label>
              <input
                type="number"
                value={topN}
                onChange={(e) => setTopN(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm"
                min={1}
                step={1}
              />
              <p className="text-[11px] text-slate-500 mt-1">
                Number of tickers in the basket at each rebalance.
              </p>
            </div>
          </div>
        </div>

        {/* Save row */}
        <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between">
          <div className="flex flex-1 gap-2 items-center">
            <input
              value={configName}
              onChange={(e) => setConfigName(e.target.value)}
              placeholder="Name this backtest (e.g. 'Top3 weekly semis')"
              className="flex-1 bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm"
            />
            <button
              type="button"
              onClick={saveConfig}
              className="px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs"
            >
              Save config
            </button>
          </div>
          <button
            type="submit"
            disabled={loading}
            className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-60 text-sm"
          >
            {loading ? "Running..." : "Run backtest"}
          </button>
        </div>

        {(err || saveErr) && (
          <div className="bg-rose-950/40 border border-rose-900 text-rose-200 text-xs rounded-xl p-3 mt-2">
            {err && <>Backtest error: {err}<br /></>}
            {saveErr && <>Save error: {saveErr}</>}
          </div>
        )}
      </form>

      {/* Saved backtests */}
      {configs.length > 0 && (
        <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-4">
          <div className="flex items-center justify-between mb-2">
            <div className="text-sm font-semibold">Saved backtests</div>
            <div className="text-[11px] text-slate-500">
              Click “Load” to populate the form, or “Run” to load + run.
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="text-slate-400 border-b border-slate-800">
                <tr className="text-left">
                  <th className="py-2 pr-2">Name</th>
                  <th className="py-2 pr-2">Tickers</th>
                  <th className="py-2 pr-2">Window</th>
                  <th className="py-2 pr-2">Params</th>
                  <th className="py-2 pr-2 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {configs.map((cfg) => (
                  <tr
                    key={cfg.id}
                    className="border-t border-slate-900 hover:bg-slate-900/60"
                  >
                    <td className="py-1.5 pr-2 font-semibold">
                      {cfg.name}
                    </td>
                    <td className="py-1.5 pr-2">
                      {cfg.tickers}
                    </td>
                    <td className="py-1.5 pr-2">
                      {cfg.start} → {cfg.end}
                    </td>
                    <td className="py-1.5 pr-2">
                      ${cfg.initial_capital.toFixed(0)} · reb {cfg.rebalance_days}d · top{" "}
                      {cfg.top_n ?? "all"}
                    </td>
                    <td className="py-1.5 pr-2 text-right">
                      <div className="inline-flex gap-2">
                        <button
                          type="button"
                          onClick={() => applyConfig(cfg)}
                          className="px-2 py-1 rounded-lg border border-slate-700 hover:bg-slate-800"
                        >
                          Load
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            applyConfig(cfg);
                            runBacktest(null, true);
                          }}
                          className="px-2 py-1 rounded-lg border border-indigo-600 text-indigo-200 hover:bg-indigo-950"
                        >
                          Run
                        </button>
                        <button
                          type="button"
                          onClick={() => deleteConfig(cfg.id)}
                          className="px-2 py-1 rounded-lg border border-rose-900 text-rose-200 hover:bg-rose-950"
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Summary + chart + per-ticker section (unchanged from last version) */}
      {result && (
        <>
          <div className="grid lg:grid-cols-3 gap-4">
            {/* Metrics */}
            <div className="lg:col-span-1 space-y-3">
              <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-4">
                <div className="text-sm font-semibold mb-2">
                  Summary
                </div>
                {summary ? (
                  <div className="space-y-1 text-xs">
                    <Row
                      k="Initial capital"
                      v={`$${summary.initial_capital.toFixed(2)}`}
                    />
                    <Row
                      k="Final value"
                      v={`$${summary.final_value.toFixed(2)}`}
                    />
                    <Row
                      k="Total return"
                      v={pct(summary.total_return)}
                    />
                    <Row
                      k="Benchmark return"
                      v={pct(summary.benchmark_return)}
                    />
                    <Row
                      k="Alpha"
                      v={pct(summary.alpha)}
                    />
                    <Row
                      k="CAGR"
                      v={pct(summary.cagr)}
                    />
                    <Row
                      k="Volatility (ann.)"
                      v={pct(summary.volatility_annual)}
                    />
                    <Row
                      k="Sharpe (approx.)"
                      v={summary.sharpe_like.toFixed(2)}
                    />
                    <Row
                      k="Max drawdown"
                      v={pct(summary.max_drawdown)}
                    />
                  </div>
                ) : (
                  <div className="text-xs text-slate-500">
                    No summary returned.
                  </div>
                )}
              </div>

              <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-4 text-xs text-slate-400">
                <div className="font-semibold mb-1">Notes</div>
                <ul className="list-disc pl-4 space-y-1">
                  <li>Universe is the tickers you specify.</li>
                  <li>
                    Every rebalance, the strategy picks Top N by simple
                    momentum over a short lookback.
                  </li>
                  <li>
                    Between rebalances, it holds those names equal-weight.
                  </li>
                </ul>
              </div>
            </div>

            {/* Chart */}
            <div className="lg:col-span-2 bg-slate-900/50 border border-slate-800 rounded-2xl p-4">
              <div className="text-sm font-semibold mb-2">Equity curve</div>
              {chartData.length ? (
                <div className="w-full h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                      <YAxis tick={{ fontSize: 10 }} />
                      <Tooltip />
                      <Legend />
                      <Line
                        type="monotone"
                        dataKey="portfolio"
                        name="Portfolio"
                        strokeWidth={2}
                        dot={false}
                      />
                      <Line
                        type="monotone"
                        dataKey="benchmark"
                        name={result?.benchmark?.symbol || "Benchmark"}
                        strokeWidth={2}
                        strokeDasharray="4 2"
                        dot={false}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <div className="text-xs text-slate-500">
                  No equity curve data returned.
                </div>
              )}
            </div>
          </div>

          {/* Per-ticker stats */}
          {perTicker.length > 0 && (
            <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-4">
              <div className="flex items-center justify-between mb-2">
                <div className="text-sm font-semibold">
                  Per-ticker stats (buy &amp; hold over window)
                </div>
                <div className="text-[11px] text-slate-500">
                  Use this to see which names are actually carrying the strategy.
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead className="text-slate-400 border-b border-slate-800">
                    <tr className="text-left">
                      <th className="py-2 pr-2">Symbol</th>
                      <th className="py-2 pr-2">Total return</th>
                      <th className="py-2 pr-2">Vol (ann.)</th>
                      <th className="py-2 pr-2">Sharpe-like</th>
                      <th className="py-2 pr-2">Max drawdown</th>
                    </tr>
                  </thead>
                  <tbody>
                    {perTicker.map((row) => (
                      <tr
                        key={row.symbol}
                        className="border-t border-slate-900 hover:bg-slate-900/60"
                      >
                        <td className="py-1.5 pr-2 font-semibold">
                          {row.symbol}
                        </td>
                        <td className="py-1.5 pr-2">
                          {pct(row.total_return)}
                        </td>
                        <td className="py-1.5 pr-2">
                          {pct(row.volatility_annual)}
                        </td>
                        <td className="py-1.5 pr-2">
                          {row.sharpe_like.toFixed(2)}
                        </td>
                        <td className="py-1.5 pr-2">
                          {pct(row.max_drawdown)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function Row({ k, v }) {
  return (
    <div className="flex justify-between">
      <span className="text-slate-400">{k}</span>
      <span className="text-slate-100">{v}</span>
    </div>
  );
}

function pct(x) {
  if (typeof x !== "number" || Number.isNaN(x)) return "-";
  return `${(x * 100).toFixed(1)}%`;
}
