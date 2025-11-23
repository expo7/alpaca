import { useEffect, useMemo, useState } from "react";
import { useAuth } from "../AuthProvider.jsx";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const BASE = "http://127.0.0.1:8000";

async function apiFetch(path, token, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (options.body && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

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
      (data && (data.detail || data.error || data.message)) ||
      data.raw ||
      `HTTP ${res.status}`;
    const err = new Error(msg);
    err.payload = data;
    throw err;
  }

  return data;
}

const DEFAULT_STRATEGY_SPEC = {
  name: "RSI Bounce",
  entry_tree: {
    type: "condition",
    indicator: "rsi",
    operator: "lt",
    value: { param: "rsi_entry" },
    lookback: { param: "rsi_period" },
  },
  exit_tree: {
    type: "condition",
    indicator: "rsi",
    operator: "gt",
    value: { param: "rsi_exit" },
    lookback: { param: "rsi_period" },
  },
  parameters: {
    rsi_period: { type: "int", default: 14, min: 2, max: 50 },
    rsi_entry: { type: "float", default: 30, min: 5, max: 50 },
    rsi_exit: { type: "float", default: 55, min: 30, max: 90 },
  },
  metadata: {
    style: "mean_reversion",
    notes: "Sample RSI-based dip buyer.",
  },
};

function formatDate(offsetDays = 0) {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  return d.toISOString().slice(0, 10);
}

function pretty(obj) {
  return JSON.stringify(obj, null, 2);
}

function StatsTable({ stats }) {
  const rows = [
    { k: "Start equity", v: stats?.start_equity },
    { k: "End equity", v: stats?.end_equity },
    { k: "Return %", v: stats?.return_pct },
    { k: "Max drawdown %", v: stats?.max_drawdown_pct },
    { k: "Trades", v: stats?.num_trades },
    { k: "Win rate %", v: stats?.win_rate_pct },
  ];

  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-4">
      <div className="text-sm font-semibold mb-3">Stats</div>
      <div className="divide-y divide-slate-800 text-sm">
        {rows.map((row) => (
          <div key={row.k} className="flex items-center justify-between py-1.5">
            <span className="text-slate-400">{row.k}</span>
            <span className="text-slate-100">
              {typeof row.v === "number" ? row.v : row.v ?? "-"}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function StrategyBacktestPage() {
  const { token } = useAuth();

  const [strategyText, setStrategyText] = useState(() =>
    pretty(DEFAULT_STRATEGY_SPEC)
  );
  const [strategyErrors, setStrategyErrors] = useState([]);
  const [parseError, setParseError] = useState("");
  const [validationMsg, setValidationMsg] = useState("");
  const [backtestError, setBacktestError] = useState("");
  const [isValidating, setIsValidating] = useState(false);
  const [isRunning, setIsRunning] = useState(false);

  const [templates, setTemplates] = useState([]);
  const [selectedTemplate, setSelectedTemplate] = useState("");
  const [templateErr, setTemplateErr] = useState("");

  const [botConfig, setBotConfig] = useState({
    symbols: "AAPL,MSFT,SPY",
    start_date: formatDate(-120),
    end_date: formatDate(0),
    starting_equity: 10000,
    benchmark: "SPY",
  });

  const [result, setResult] = useState(null);

  useEffect(() => {
    if (!token) return undefined;
    let active = true;

    async function loadTemplates() {
      try {
        setTemplateErr("");
        const data = await apiFetch("/api/strategies/templates/", token);
        if (!active) return;
        setTemplates(Array.isArray(data) ? data : []);
        if (Array.isArray(data) && data.length) {
          setSelectedTemplate(data[0].id);
          setStrategyText(pretty(data[0].strategy_spec));
        }
      } catch (err) {
        if (active) setTemplateErr(err.message || "Failed to load templates");
      }
    }

    loadTemplates();
    return () => {
      active = false;
    };
  }, [token]);

  function parseStrategy() {
    setParseError("");
    try {
      return JSON.parse(strategyText);
    } catch (err) {
      setParseError(err.message);
      return null;
    }
  }

  function updateBotConfig(key, value) {
    setBotConfig((prev) => ({ ...prev, [key]: value }));
  }

  async function handleValidate() {
    const parsed = parseStrategy();
    if (!parsed) return;

    setIsValidating(true);
    setStrategyErrors([]);
    setValidationMsg("");
    setBacktestError("");

    try {
      const res = await apiFetch("/api/strategies/validate/", token, {
        method: "POST",
        body: JSON.stringify(parsed),
      });
      if (res.valid) {
        setValidationMsg("Strategy looks valid.");
      } else {
        setStrategyErrors(res.errors || []);
      }
    } catch (err) {
      if (err.payload?.errors) {
        setStrategyErrors(err.payload.errors);
      }
      setBacktestError(err.message || "Validation failed");
    } finally {
      setIsValidating(false);
    }
  }

  async function handleRun() {
    const parsed = parseStrategy();
    if (!parsed) return;

    const symbols = (botConfig.symbols || "")
      .split(",")
      .map((s) => s.trim().toUpperCase())
      .filter(Boolean);
    if (!symbols.length) {
      setStrategyErrors([{ field: "bot.symbols", message: "At least one symbol is required" }]);
      return;
    }
    if (!botConfig.start_date || !botConfig.end_date) {
      setStrategyErrors([{ field: "dates", message: "start_date and end_date are required" }]);
      return;
    }

    setIsRunning(true);
    setStrategyErrors([]);
    setBacktestError("");
    setValidationMsg("");

    try {
      const payload = {
        strategy: parsed,
        bot: {
          symbols,
          mode: "backtest",
          benchmark: botConfig.benchmark || "SPY",
          capital: Number(botConfig.starting_equity) || 0,
        },
        start_date: botConfig.start_date,
        end_date: botConfig.end_date,
      };

      const res = await apiFetch("/api/backtests/run/", token, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setResult(res);
    } catch (err) {
      if (err.payload?.errors) {
        setStrategyErrors(err.payload.errors);
      }
      setBacktestError(err.message || "Backtest failed");
    } finally {
      setIsRunning(false);
    }
  }

  function applyTemplate(tpl) {
    setSelectedTemplate(tpl.id);
    setStrategyText(pretty(tpl.strategy_spec));
    setStrategyErrors([]);
    setValidationMsg("");
    setParseError("");
  }

  const chartData = useMemo(() => {
    const eq = result?.equity_curve || [];
    return eq.map((pt) => ({
      date: (pt.date || "").slice(0, 10),
      value: pt.value,
    }));
  }, [result]);

  const trades = result?.trades || [];

  return (
    <div className="space-y-4">
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-4 flex flex-col gap-1">
        <div className="text-lg font-semibold">Strategy Backtest (Experimental)</div>
        <div className="text-sm text-amber-300">
          No auto-runs. Validate and run manually to avoid surprise data fetches.
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 space-y-3">
          <div className="grid md:grid-cols-[220px,1fr] gap-3">
            <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-3 space-y-2">
              <div className="flex items-center justify-between">
                <div className="text-sm font-semibold">Templates</div>
                {templateErr && (
                  <span className="text-[11px] text-rose-300">{templateErr}</span>
                )}
              </div>
              {templates.map((tpl) => (
                <button
                  key={tpl.id}
                  type="button"
                  onClick={() => applyTemplate(tpl)}
                  className={`w-full text-left px-3 py-2 rounded-xl border transition ${
                    selectedTemplate === tpl.id
                      ? "border-amber-400/70 bg-amber-400/10 text-amber-100"
                      : "border-slate-800 bg-slate-950 hover:border-slate-700 text-slate-200"
                  }`}
                >
                  <div className="font-semibold text-sm">{tpl.name}</div>
                  <div className="text-[11px] text-slate-400">{tpl.description}</div>
                </button>
              ))}
              {!templates.length && !templateErr && (
                <div className="text-xs text-slate-500">Loading templates...</div>
              )}
            </div>

            <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-3">
              <div className="flex items-center justify-between mb-2">
                <div>
                  <div className="text-sm font-semibold">StrategySpec JSON</div>
                  <div className="text-[11px] text-slate-400">
                    Edit freely or start from a template.
                  </div>
                </div>
                <button
                  type="button"
                  onClick={handleValidate}
                  disabled={isValidating}
                  className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-60 text-xs"
                >
                  {isValidating ? "Validating..." : "Validate Strategy"}
                </button>
              </div>

              <textarea
                value={strategyText}
                onChange={(e) => setStrategyText(e.target.value)}
                rows={18}
                className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 font-mono text-xs text-slate-100 focus:border-amber-500 focus:outline-none"
              />

              {parseError && (
                <div className="mt-2 text-xs text-rose-300">
                  JSON parse error: {parseError}
                </div>
              )}
              {validationMsg && (
                <div className="mt-2 text-xs text-emerald-300">{validationMsg}</div>
              )}
              {strategyErrors.length > 0 && (
                <div className="mt-2 text-xs text-amber-200 space-y-1">
                  {strategyErrors.map((err, idx) => (
                    <div key={`${err.field}-${idx}`}>
                      {err.field}: {err.message}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="space-y-3">
          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-4 space-y-3">
            <div className="text-sm font-semibold">Bot config (backtest)</div>
            <div className="space-y-2 text-sm">
              <label className="block">
                <span className="text-xs text-slate-400">Symbols (comma-separated)</span>
                <input
                  value={botConfig.symbols}
                  onChange={(e) => updateBotConfig("symbols", e.target.value)}
                  className="mt-1 w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm"
                  placeholder="AAPL, MSFT, SPY"
                />
              </label>

              <div className="grid grid-cols-2 gap-2">
                <label className="block">
                  <span className="text-xs text-slate-400">Start date</span>
                  <input
                    type="date"
                    value={botConfig.start_date}
                    onChange={(e) => updateBotConfig("start_date", e.target.value)}
                    className="mt-1 w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm"
                  />
                </label>
                <label className="block">
                  <span className="text-xs text-slate-400">End date</span>
                  <input
                    type="date"
                    value={botConfig.end_date}
                    onChange={(e) => updateBotConfig("end_date", e.target.value)}
                    className="mt-1 w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm"
                  />
                </label>
              </div>

              <label className="block">
                <span className="text-xs text-slate-400">Starting equity</span>
                <input
                  type="number"
                  min={0}
                  value={botConfig.starting_equity}
                  onChange={(e) => updateBotConfig("starting_equity", e.target.value)}
                  className="mt-1 w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm"
                />
              </label>

              <label className="block">
                <span className="text-xs text-slate-400">Mode</span>
                <input
                  value="backtest"
                  readOnly
                  className="mt-1 w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm text-slate-400"
                />
              </label>
            </div>

            <button
              type="button"
              onClick={handleRun}
              disabled={isRunning}
              className="w-full px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-60 text-sm font-semibold"
            >
              {isRunning ? "Running…" : "Run Backtest"}
            </button>
            {backtestError && (
              <div className="text-xs text-rose-300">{backtestError}</div>
            )}
          </div>

          {result && <StatsTable stats={result.stats || {}} />}
        </div>
      </div>

      {result?.equity_curve && result.equity_curve.length > 0 && (
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-4">
          <div className="text-sm font-semibold mb-2">Equity curve</div>
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
                  dataKey="value"
                  name="Equity"
                  strokeWidth={2}
                  stroke="#a78bfa"
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {trades.length > 0 && (
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-4">
          <div className="text-sm font-semibold mb-3">Trades</div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="text-slate-400 border-b border-slate-800">
                <tr className="text-left">
                  <th className="py-2 pr-2">Symbol</th>
                  <th className="py-2 pr-2">Action</th>
                  <th className="py-2 pr-2">Qty</th>
                  <th className="py-2 pr-2">Price</th>
                  <th className="py-2 pr-2">Timestamp</th>
                </tr>
              </thead>
              <tbody>
                {trades.map((t, idx) => (
                  <tr
                    key={`${t.symbol || "trade"}-${idx}`}
                    className="border-t border-slate-900 hover:bg-slate-900/50"
                  >
                    <td className="py-1.5 pr-2 font-semibold">
                      {t.symbol || "-"}
                    </td>
                    <td className="py-1.5 pr-2">{t.action || t.side || "-"}</td>
                    <td className="py-1.5 pr-2">{t.qty ?? t.quantity ?? "-"}</td>
                    <td className="py-1.5 pr-2">
                      {typeof t.price === "number" ? t.price : t.fill_price ?? "-"}
                    </td>
                    <td className="py-1.5 pr-2">
                      {t.timestamp || t.time || "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
