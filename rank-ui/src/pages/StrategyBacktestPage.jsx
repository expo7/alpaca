import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "../AuthProvider.jsx";
import { validateStrategy, runBacktest, createBatchBacktest, getBatchBacktest } from "../api/backtests.js";
import { createBot } from "../api/bots.js";
import { STRATEGY_TEMPLATES } from "../strategies/templates.js";
import BacktestChart from "../components/backtest/BacktestChart.jsx";
import BacktestStatsPanel from "../components/backtest/BacktestStatsPanel.jsx";
import BacktestOrdersTable from "../components/backtest/BacktestOrdersTable.jsx";
import BacktestControls from "../components/backtest/BacktestControls.jsx";
import normalizeCandles from "../components/backtest/utils/normalizeCandles.js";
import normalizeOrders from "../components/backtest/utils/normalizeOrders.js";
import mergeOrdersIntoCandles from "../components/backtest/utils/mergeOrdersIntoCandles.js";

const BASE = "http://127.0.0.1:8000";

const DEFAULT_TEMPLATE = STRATEGY_TEMPLATES[0];

function formatDate(offsetDays = 0) {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  return d.toISOString().slice(0, 10);
}

function pretty(obj) {
  return JSON.stringify(obj, null, 2);
}
export default function StrategyBacktestPage({ onNavigate }) {
  const { token } = useAuth();

  const [selectedTemplateId, setSelectedTemplateId] = useState(DEFAULT_TEMPLATE.id);
  const [strategyText, setStrategyText] = useState(() =>
    pretty(DEFAULT_TEMPLATE.spec)
  );
  const [strategyErrors, setStrategyErrors] = useState([]);
  const [parseError, setParseError] = useState("");
  const [validationMsg, setValidationMsg] = useState("");
  const [backtestError, setBacktestError] = useState("");
  const [isValidating, setIsValidating] = useState(false);
  const [isRunning, setIsRunning] = useState(false);

  const [templates, setTemplates] = useState(STRATEGY_TEMPLATES);
  const [selectedTemplate, setSelectedTemplate] = useState(DEFAULT_TEMPLATE.id);
  const [templateErr, setTemplateErr] = useState("");

  const [botConfig, setBotConfig] = useState({
    symbols: "AAPL",
    start_date: formatDate(-365),
    end_date: formatDate(0),
    starting_equity: 10000,
    rebalance_days: 5,
    disableRebalance: true,
    benchmark: "SPY",
    commission_per_trade: "",
    commission_pct: "",
    slippage_bps: "",
  });

  const [result, setResult] = useState(null);

  // Batch state
  const [paramGridRows, setParamGridRows] = useState([{ name: "", values: "" }]);
  const [batchLabel, setBatchLabel] = useState("");
  const [batchId, setBatchId] = useState("");
  const [batchStatus, setBatchStatus] = useState("");
  const [batchRuns, setBatchRuns] = useState([]);
  const [batchError, setBatchError] = useState("");
  const [promoteModal, setPromoteModal] = useState({
    open: false,
    run: null,
    name: "",
    mode: "paper",
    saving: false,
    error: "",
  });
  const [singleBotModal, setSingleBotModal] = useState({
    open: false,
    name: "",
    mode: "paper",
    saving: false,
    error: "",
  });
  const [sortField, setSortField] = useState("sharpe_ratio");
  const [sortDir, setSortDir] = useState("desc");
  const [minTrades, setMinTrades] = useState(0);
  const [chartSymbol, setChartSymbol] = useState("AAPL");
  const [priceData, setPriceData] = useState([]);
  const [chartLoading, setChartLoading] = useState(false);
  const [chartError, setChartError] = useState("");
  const strategyIndicators = useMemo(() => {
    const flags = { sma: false, rsi: false, macd: false, rsi_entry: null, rsi_exit: null };
    try {
      const parsed = JSON.parse(strategyText || "{}");
      const params = parsed.parameters || {};
      const markIndicator = (name) => {
        const key = (name || "").toLowerCase();
        if (key.includes("sma")) flags.sma = true;
        if (key === "rsi") flags.rsi = true;
        if (key === "macd") flags.macd = true;
      };
      const walk = (node) => {
        if (!node) return;
        if (Array.isArray(node)) {
          node.forEach(walk);
          return;
        }
        if (typeof node === "object") {
          if (node.indicator) markIndicator(node.indicator);
          if (node.left) markIndicator(node.left);
          Object.values(node).forEach(walk);
        }
      };
      walk(parsed.entry_tree);
      walk(parsed.exit_tree);
      Object.keys(params).forEach(markIndicator);
      const entry = params.rsi_entry_level?.default ?? params.rsi_entry_level ?? null;
      const exit = params.rsi_exit_level?.default ?? params.rsi_exit_level ?? null;
      flags.rsi_entry = entry != null ? Number(entry) : null;
      flags.rsi_exit = exit != null ? Number(exit) : null;
    } catch {
      // ignore parse errors
    }
    return flags;
  }, [strategyText]);
  const sortedRuns = useMemo(() => {
    const completed = (batchRuns || []).filter(
      (r) =>
        r.status === "completed" &&
        r.stats &&
        (minTrades ? (r.stats.num_trades || 0) >= Number(minTrades) : true)
    );

    const getMetric = (run) => {
      const s = run.stats || {};
      switch (sortField) {
        case "return_pct":
          return s.return_pct ?? s.total_return ?? 0;
        case "max_drawdown_pct":
          return s.max_drawdown_pct ?? s.max_drawdown ?? 0;
        case "num_trades":
          return s.num_trades ?? 0;
        case "sharpe_ratio":
        default:
          return s.sharpe_ratio ?? s.sharpe_like ?? 0;
      }
    };

    completed.sort((a, b) => {
      const av = getMetric(a);
      const bv = getMetric(b);
      if (av === bv) return 0;
      if (sortDir === "desc") return bv - av;
      return av - bv;
    });

    const best = completed.length ? completed[0] : null;
    return { completed, best };
  }, [batchRuns, sortField, sortDir, minTrades]);

  useEffect(() => {
    if (!token) return undefined;
    let active = true;

    async function loadTemplates() {
      try {
        setTemplateErr("");
        const res = await fetch("http://127.0.0.1:8000/api/strategies/templates/", {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        let data = [];
        try {
          if (res.json) {
            data = await res.json();
          } else {
            const txt = await res.text();
            data = txt ? JSON.parse(txt) : [];
          }
        } catch {
          const txt = await res.text();
          data = txt ? JSON.parse(txt) : [];
        }
        if (!active) return;
        const merged = [...STRATEGY_TEMPLATES];
        (Array.isArray(data) ? data : []).forEach((tpl) => {
          if (!merged.some((t) => t.id === tpl.id)) {
            merged.push({ ...tpl, spec: tpl.strategy_spec || tpl.spec });
          }
        });
        setTemplates(merged);
        if (!selectedTemplateId && merged.length) {
          setSelectedTemplateId(merged[0].id);
          setSelectedTemplate(merged[0].id);
          setStrategyText(pretty(merged[0].spec));
        }
      } catch (err) {
        if (active) setTemplateErr(err.message || "Failed to load templates");
      }
    }

    loadTemplates();
    return () => {
      active = false;
    };
    // we intentionally do not reset on template id change to preserve user edits
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  function parseStrategy() {
    setParseError("");
    try {
      return JSON.parse(strategyText);
    } catch (err) {
      setParseError(err.message);
      setSelectedTemplateId("custom");
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
      const res = await validateStrategy(parsed, token);
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
          rebalance_days:
            botConfig.disableRebalance === true
              ? undefined
              : botConfig.rebalance_days
                ? Number(botConfig.rebalance_days)
                : undefined,
          top_n:
            botConfig.disableRebalance === true
              ? undefined
              : botConfig.top_n
                ? Number(botConfig.top_n)
                : undefined,
          commission_per_trade: botConfig.commission_per_trade
            ? Number(botConfig.commission_per_trade)
            : undefined,
          commission_pct: botConfig.commission_pct
            ? Number(botConfig.commission_pct)
            : undefined,
          slippage_bps: botConfig.slippage_bps ? Number(botConfig.slippage_bps) : undefined,
        },
        start_date: botConfig.start_date,
        end_date: botConfig.end_date,
      };

      const res = await runBacktest(parsed, payload.bot, payload.start_date, payload.end_date, token);
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
    const spec = tpl?.strategy_spec || tpl?.spec;
    if (!spec) return;
    setSelectedTemplate(tpl.id);
    setSelectedTemplateId(tpl.id);
    const defaultSym = (botConfig.symbols || "").split(",").map((s) => s.trim()).filter(Boolean)[0];
    if (defaultSym) setChartSymbol(defaultSym.toUpperCase());
    setStrategyText(pretty(spec));
    setStrategyErrors([]);
    setValidationMsg("");
    setParseError("");
  }

  function paramGridToObject() {
    const grid = {};
    for (const row of paramGridRows) {
      if (!row.name.trim()) continue;
      const nums = row.values
        .split(",")
        .map((v) => v.trim())
        .filter(Boolean)
        .map((v) => Number(v))
        .filter((v) => !Number.isNaN(v));
      if (nums.length) grid[row.name.trim()] = nums;
    }
    return grid;
  }

  async function handleBatchRun() {
    const parsed = parseStrategy();
    if (!parsed) return;

    const symbols = (botConfig.symbols || "")
      .split(",")
      .map((s) => s.trim().toUpperCase())
      .filter(Boolean);
    if (!symbols.length) {
      setBatchError("At least one symbol is required.");
      return;
    }

    const grid = paramGridToObject();
    setBatchError("");
    try {
      const payload = {
        strategy: parsed,
        bot: {
          symbols,
          mode: "backtest",
          benchmark: botConfig.benchmark || "SPY",
          capital: Number(botConfig.starting_equity) || 0,
          rebalance_days:
            botConfig.disableRebalance === true
              ? undefined
              : botConfig.rebalance_days
                ? Number(botConfig.rebalance_days)
                : undefined,
          top_n:
            botConfig.disableRebalance === true
              ? undefined
              : botConfig.top_n
                ? Number(botConfig.top_n)
                : undefined,
          commission_per_trade: botConfig.commission_per_trade
            ? Number(botConfig.commission_per_trade)
            : undefined,
          commission_pct: botConfig.commission_pct
            ? Number(botConfig.commission_pct)
            : undefined,
          slippage_bps: botConfig.slippage_bps ? Number(botConfig.slippage_bps) : undefined,
        },
        param_grid: grid,
        start_date: botConfig.start_date,
        end_date: botConfig.end_date,
        label: batchLabel,
      };
      const res = await createBatchBacktest(payload, token);
      setBatchId(String(res.batch_id));
      setBatchStatus(res.status);
      setBatchRuns([]);
    } catch (err) {
      if (err.payload?.errors) {
        setStrategyErrors(err.payload.errors);
      }
      setBatchError(err.message || "Batch request failed");
    }
  }

  useEffect(() => {
    const first = (botConfig.symbols || "")
      .split(",")
      .map((s) => s.trim().toUpperCase())
      .filter(Boolean)[0];
    if (first && !chartSymbol) {
      setChartSymbol(first);
    }


  }, [botConfig.symbols, chartSymbol]);

  const trades = useMemo(() => result?.trades || [], [result]);
  const normalizedCandles = useMemo(() => normalizeCandles(priceData), [priceData]);
  const normalizedOrders = useMemo(() => normalizeOrders(trades, normalizedCandles), [trades, normalizedCandles]);

  // Helper: lightweight console diagnostics for chart data shape
  const logChartData = useCallback((label, data) => {
    if (!Array.isArray(data)) {
      console.log(`[ChartData] ${label}: not an array`, data);
      return;
    }
    const sample = data.slice(0, 3);
    const keys = sample[0] ? Object.keys(sample[0]) : [];
    console.log(`[ChartData] ${label}: length=${data.length}, keys=${keys.join(",")}`);
    sample.forEach((row, idx) => {
      const typed = Object.fromEntries(Object.entries(row || {}).map(([k, v]) => [k, typeof v]));
      console.log(`[ChartData] ${label} sample[${idx}]`, row, typed);
    });
  }, []);
  const priceChartDataFull = useMemo(() => {
    const symbol = (chartSymbol || "").toUpperCase();
    const base = normalizedCandles
      .filter((c) => {
        if (!symbol) return true;
        return (c.symbol || "").toUpperCase() === symbol || !c.symbol;
      })
      .map((c) => ({
        ...c,
        barIndex: c.barIndex,
        timestamp: c.timestamp || c.date,
        sma20: c.sma_fast,
        sma50: c.sma_slow,
        macdSignal: c.macd_signal,
      }));
    const filteredOrders = normalizedOrders.filter((o) => {
      if (!symbol) return true;
      const osym = (o.symbol || "").toUpperCase();
      return !osym || osym === symbol;
    });
    return mergeOrdersIntoCandles(base, filteredOrders);
  }, [chartSymbol, normalizedCandles, normalizedOrders]);

  const rsiBuyLevel =
    strategyIndicators.rsi_entry != null ? Number(strategyIndicators.rsi_entry) : undefined;
  const rsiSellLevel =
    strategyIndicators.rsi_exit != null ? Number(strategyIndicators.rsi_exit) : undefined;

  const equityDataFull = useMemo(() => {
    const eq = result?.equity_curve || [];
    return eq
      .map((pt, idx) => {
        const tsVal = pt.date || pt.time || null;
        const tsNum = tsVal ? new Date(tsVal).getTime() : idx;
        return {
          timestamp: tsVal ? String(tsVal).slice(0, 10) : String(idx),
          ts: tsNum,
          barIndex: idx,
          equity: Number(pt.value ?? pt.equity ?? pt.amount ?? 0),
        };
      })
      .filter((p) => Number.isFinite(p.ts) && Number.isFinite(p.equity));
  }, [result]);

  const { alignedPriceData, alignedEquityData } = useMemo(() => {
    const priceBarIndexes = priceChartDataFull.map((p) => p.barIndex);
    const equityBarIndexes = equityDataFull.map((e) => e.barIndex);

    const priceStart = priceBarIndexes.length ? Math.min(...priceBarIndexes) : null;
    const priceEnd = priceBarIndexes.length ? Math.max(...priceBarIndexes) : null;

    const rsiBarIndexes = priceChartDataFull
      .filter((p) => typeof p.rsi === "number" && !Number.isNaN(p.rsi))
      .map((p) => p.barIndex);
    const rsiStart = rsiBarIndexes.length ? Math.min(...rsiBarIndexes) : null;

    const equityStart = equityBarIndexes.length ? Math.min(...equityBarIndexes) : null;
    const equityEnd = equityBarIndexes.length ? Math.max(...equityBarIndexes) : null;

    const starts = [priceStart, rsiStart, equityStart].filter((v) => v != null);
    const globalStart = starts.length ? Math.max(...starts) : null;

    const ends = [priceEnd, equityEnd].filter((v) => v != null);
    const globalEnd = ends.length ? Math.min(...ends) : null;

    if (globalStart == null || globalEnd == null || globalStart >= globalEnd) {
      console.log("[ChartData] alignment skipped", { priceStart, rsiStart, equityStart, priceEnd, equityEnd });
      return { alignedPriceData: priceChartDataFull, alignedEquityData: equityDataFull };
    }

    console.log("[ChartData] alignment range", { globalStart, globalEnd, priceStart, rsiStart, equityStart, priceEnd, equityEnd });

    return {
      alignedPriceData: priceChartDataFull.filter(
        (p) => p.barIndex >= globalStart && p.barIndex <= globalEnd
      ),
      alignedEquityData: equityDataFull.filter(
        (e) => e.barIndex >= globalStart && e.barIndex <= globalEnd
      ),
    };
  }, [priceChartDataFull, equityDataFull]);

  const chartSymbols = useMemo(
    () =>
      (botConfig.symbols || "")
        .split(",")
        .map((s) => s.trim().toUpperCase())
        .filter(Boolean),
    [botConfig.symbols]
  );

  useEffect(() => {
    logChartData("priceChartDataFull", priceChartDataFull);
    logChartData("equityDataFull", equityDataFull);
    logChartData("alignedPriceData", alignedPriceData);
    logChartData("alignedEquityData", alignedEquityData);
  }, [priceChartDataFull, equityDataFull, alignedPriceData, alignedEquityData, logChartData]);


  const loadChartData = useCallback(
    async (symbol) => {
      if (!token || !symbol) return;
      setChartLoading(true);
      setChartError("");
      try {
        const params = new URLSearchParams();
        params.set("interval", "1d");
        if (botConfig.start_date) params.set("start", botConfig.start_date);
        if (botConfig.end_date) params.set("end", botConfig.end_date);
        const res = await fetch(
          `${BASE}/api/paper/symbols/${encodeURIComponent(symbol)}/interval/?${params.toString()}`,
          {
            headers: { Authorization: `Bearer ${token}` },
          }
        );
        const data = await res.json();
        if (!res.ok) throw new Error(data?.detail || "Failed to load price data");
        const candles = Array.isArray(data.candles) ? data.candles : [];
        const mapped = candles
          .map((c) => {
            if (Array.isArray(c)) {
              const [t, o, h, l, cl] = c;
              return {
                date: new Date(t).toISOString().slice(0, 10),
                open: Number(o),
                high: Number(h),
                low: Number(l),
                close: Number(cl),
              };
            }
            return {
              date: (c.t || c.time || c.timestamp || "").slice(0, 10),
              open: c.open != null ? Number(c.open) : c.o != null ? Number(c.o) : null,
              high: c.high != null ? Number(c.high) : c.h != null ? Number(c.h) : null,
              low: c.low != null ? Number(c.low) : c.l != null ? Number(c.l) : null,
              close: c.close != null ? Number(c.close) : c.c != null ? Number(c.c) : null,
            };
          })
          .filter((d) => d.date && Number.isFinite(d.close));
        // compute indicators based on common params
        const fastLen = strategyIndicators.sma ? Number(botConfig.fast_length || 20) || 20 : null;
        const slowLen = strategyIndicators.sma ? Number(botConfig.slow_length || 50) || 50 : null;
        const rsiLen = strategyIndicators.rsi ? Number(botConfig.rsi_period || 14) || 14 : null;
        const macdFast = 12;
        const macdSlow = 26;
        const macdSignal = 9;

        // helpers
        const ema = (arr, period) => {
          if (!arr.length || period <= 0) return [];
          const k = 2 / (period + 1);
          const out = [];
          let prev = arr[0];
          out.push(prev);
          for (let i = 1; i < arr.length; i += 1) {
            prev = arr[i] * k + prev * (1 - k);
            out.push(prev);
          }
          return out;
        };

        const closes = mapped.map((r) => Number(r.close || 0));
        const macdArr = [];
        const macdSignalArr = [];
        if (closes.length) {
          const emaFast = ema(closes, macdFast);
          const emaSlow = ema(closes, macdSlow);
          for (let i = 0; i < closes.length; i += 1) {
            macdArr[i] = emaFast[i] - emaSlow[i];
          }
          const signal = ema(macdArr, macdSignal);
          for (let i = 0; i < macdArr.length; i += 1) {
            macdSignalArr[i] = signal[i];
          }
        }

        const withInd = mapped.map((row, idx, arr) => {
          const sliceFast = arr.slice(Math.max(0, idx - (fastLen - 1)), idx + 1);
          const sliceSlow = arr.slice(Math.max(0, idx - (slowLen - 1)), idx + 1);
          const smaFast =
            fastLen && sliceFast.length >= fastLen
              ? sliceFast.reduce((sum, r) => sum + Number(r.close || 0), 0) / sliceFast.length
              : null;
          const smaSlow =
            slowLen && sliceSlow.length >= slowLen
              ? sliceSlow.reduce((sum, r) => sum + Number(r.close || 0), 0) / sliceSlow.length
              : null;

          let rsi = null;
          if (rsiLen && idx + 1 >= rsiLen) {
            const window = closes.slice(Math.max(0, idx - (rsiLen - 1)), idx + 1);
            const gains = [];
            const losses = [];
            for (let i = 1; i < window.length; i += 1) {
              const diff = window[i] - window[i - 1];
              if (diff >= 0) gains.push(diff);
              else losses.push(Math.abs(diff));
            }
            const avgGain = gains.length ? gains.reduce((a, b) => a + b, 0) / gains.length : 0;
            const avgLoss = losses.length ? losses.reduce((a, b) => a + b, 0) / losses.length : 0;
            if (avgLoss !== 0) {
              const rs = avgGain / avgLoss;
              rsi = 100 - 100 / (1 + rs);
            } else if (avgGain !== 0) {
              rsi = 100;
            }
          }

          return {
            ...row,
            sma_fast: smaFast != null ? Number(smaFast.toFixed(2)) : null,
            sma_slow: smaSlow != null ? Number(smaSlow.toFixed(2)) : null,
            rsi: rsi != null ? Number(rsi.toFixed(2)) : null,
            macd: strategyIndicators.macd && macdArr[idx] != null ? Number(macdArr[idx].toFixed(2)) : null,
            macd_signal:
              strategyIndicators.macd && macdSignalArr[idx] != null ? Number(macdSignalArr[idx].toFixed(2)) : null,
          };
        });

        // map trades into markers and holding periods
        const intervals = trades
          .map((t) => {
            const entry = (t.entry_time || t.timestamp || t.time || "").slice(0, 10);
            const exit = (t.exit_time || "").slice(0, 10) || null;
            if (!entry) return null;
            return { entry, exit };
          })
          .filter(Boolean);

        const withMarkers = withInd.map((row) => {
          const d = row.date;
          const isBuy = intervals.some((i) => i.entry === d);
          const isSell = intervals.some((i) => i.exit === d);
          const inPosition = intervals.some((i) => {
            if (!i.entry) return false;
            if (i.exit) return d >= i.entry && d <= i.exit;
            return d >= i.entry;
          });
          return {
            ...row,
            buy_marker: isBuy ? row.close : null,
            sell_marker: isSell ? row.close : null,
            in_position: inPosition,
          };
        });
        const withSegments = withMarkers.map((row) => ({
          ...row,
          close_in_position: row.in_position ? row.close : null,
          close_out_position: row.in_position ? null : row.close,
        }));

        setPriceData(withSegments);
      } catch (err) {
        setChartError(err.message || "Failed to load chart");
        setPriceData([]);
      } finally {
        setChartLoading(false);
      }
    },
    [token, botConfig.start_date, botConfig.end_date, strategyIndicators.sma, strategyIndicators.rsi, strategyIndicators.macd, trades]
  );

  // Chart data now loads only when the user clicks "Load chart" to avoid extra fetches during typing.

  async function handleBatchRefresh() {
    if (!batchId) {
      setBatchError("Enter a batch id to refresh.");
      return;
    }
    setBatchError("");
    try {
      const res = await getBatchBacktest(batchId, token);
      setBatchStatus(res.status);
      setBatchRuns(res.runs || []);
      setBatchLabel(res.label || batchLabel);
    } catch (err) {
      setBatchError(err.message || "Failed to load batch");
    }
  }

  function applyParamsToStrategy(baseStrategy, params) {
    const updated = { ...(baseStrategy || {}) };
    const paramsObj = { ...((baseStrategy || {}).parameters || {}) };
    Object.entries(params || {}).forEach(([key, val]) => {
      if (paramsObj[key]) {
        paramsObj[key] = { ...paramsObj[key], default: val };
      }
    });
    updated.parameters = paramsObj;
    return updated;
  }

  function buildBotPayload(mode) {
    const symbols = (botConfig.symbols || "")
      .split(",")
      .map((s) => s.trim().toUpperCase())
      .filter(Boolean);
    const topN =
      botConfig.disableRebalance === true
        ? undefined
        : botConfig.top_n
          ? Number(botConfig.top_n)
          : undefined;
    return {
      symbols,
      mode,
      benchmark: botConfig.benchmark || "SPY",
      capital: Number(botConfig.starting_equity) || 0,
      rebalance_days:
        botConfig.disableRebalance === true
          ? undefined
          : botConfig.rebalance_days
            ? Number(botConfig.rebalance_days)
            : undefined,
      top_n: topN,
      commission_per_trade: botConfig.commission_per_trade
        ? Number(botConfig.commission_per_trade)
        : undefined,
      commission_pct: botConfig.commission_pct ? Number(botConfig.commission_pct) : undefined,
      slippage_bps: botConfig.slippage_bps ? Number(botConfig.slippage_bps) : undefined,
    };
  }

  async function promoteRunToBot(run) {
    const parsedStrategy = parseStrategy();
    if (!parsedStrategy) return;
    const botPayload = buildBotPayload(promoteModal.mode);

    const strategyWithParams = applyParamsToStrategy(parsedStrategy, run.params || {});

    setPromoteModal((m) => ({ ...m, saving: true, error: "" }));
    try {
      await createBot(
        {
          name: promoteModal.name || run.params?.name || `Bot from batch ${batchId}`,
          mode: promoteModal.mode,
          strategy: strategyWithParams,
          bot: botPayload,
        },
        token
      );
      setPromoteModal({ open: false, run: null, name: "", mode: "paper", saving: false, error: "" });
      if (onNavigate) onNavigate("bots");
    } catch (err) {
      setPromoteModal((m) => ({
        ...m,
        saving: false,
        error: err.message || "Failed to create bot",
      }));
    }
  }

  async function createBotFromResult() {
    const parsedStrategy = parseStrategy();
    if (!parsedStrategy) return;
    const botPayload = buildBotPayload(singleBotModal.mode);
    if (!botPayload.symbols.length) {
      setSingleBotModal((m) => ({ ...m, error: "Add at least one symbol." }));
      return;
    }
    setSingleBotModal((m) => ({ ...m, saving: true, error: "" }));
    try {
      await createBot(
        {
          name: singleBotModal.name || "Bot from backtest",
          mode: singleBotModal.mode,
          strategy: parsedStrategy,
          bot: botPayload,
        },
        token
      );
      setSingleBotModal({ open: false, name: "", mode: "paper", saving: false, error: "" });
      if (onNavigate) onNavigate("bots");
    } catch (err) {
      setSingleBotModal((m) => ({
        ...m,
        saving: false,
        error: err.message || "Failed to create bot",
      }));
    }
  }

  const equityCurveData = useMemo(() => {
    const eq = result?.equity_curve || [];
    return eq.map((pt) => ({
      date: (pt.date || pt.time || "").slice(0, 10),
      value: Number(pt.value ?? pt.equity ?? pt.amount ?? 0),
    }));
  }, [result]);

  return (
    <div className="space-y-4">
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-4 flex flex-col gap-1">
        <div className="text-lg font-semibold">Strategy Backtest (Experimental)</div>
        <div className="text-sm text-amber-300">
          No auto-runs. Validate and run manually to avoid surprise data fetches.
        </div>
      </div>

      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-4 text-sm">
        <div className="text-sm font-semibold mb-1">How to use this page</div>
        <ul className="list-disc ml-4 space-y-1 text-slate-300">
          <li>Pick a strategy template (or paste your own JSON) and tweak the spec.</li>
          <li>Fill in symbols, dates, capital, and costs in the Bot Config panel.</li>
          <li>Click “Validate strategy” to check the JSON before running.</li>
          <li>Click “Run backtest” to see trades and performance.</li>
          <li>Use the Batch Optimizer to sweep parameters and find a best config.</li>
          <li>Click “Create Bot” on a good run to spin up a paper bot from the Bots page.</li>
        </ul>
        <div className="text-[11px] text-slate-400 mt-2">
          This page is for research and paper trading. Live bots are gated by ALLOW_LIVE_BOTS and require extra confirmation.
        </div>
      </div>



      <BacktestControls
        botConfig={botConfig}
        onUpdateConfig={updateBotConfig}
        strategyText={strategyText}
        onStrategyTextChange={(val) => {
          setStrategyText(val);
          setSelectedTemplateId("custom");
          setSelectedTemplate("custom");
        }}
        templates={templates}
        selectedTemplateId={selectedTemplateId}
        onSelectTemplate={(tplId) => applyTemplate(templates.find((tpl) => tpl.id === tplId))}
        templateErr={templateErr}
        validationMsg={validationMsg}
        parseError={parseError}
        strategyErrors={strategyErrors}
        onValidate={handleValidate}
        onRun={handleRun}
        isValidating={isValidating}
        isRunning={isRunning}
        backtestError={backtestError}
        chartSymbol={chartSymbol}
        onChangeChartSymbol={(sym) => setChartSymbol(sym ? sym.toUpperCase() : "")}
        onLoadChart={loadChartData}
        chartLoading={chartLoading}
      />

      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-4 space-y-3">
        <div className="flex items-center justify-between">
          <div className="text-sm font-semibold">Chart: {chartSymbol || "Select symbol"}</div>
          <div className="flex items-center gap-2 text-xs">
            <select
              value={chartSymbol}
              onChange={(e) => setChartSymbol(e.target.value)}
              className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1 text-xs"
            >
              {chartSymbols.length === 0 && <option value="">No symbols</option>}
              {chartSymbols.map((sym) => (
                <option key={sym} value={sym}>
                  {sym}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => loadChartData(chartSymbol)}
              disabled={!chartSymbol || chartLoading}
              className="px-3 py-1.5 rounded-lg bg-slate-800 border border-slate-700 hover:bg-slate-700 text-xs disabled:opacity-60"
            >
              {chartLoading ? "Loading…" : "Load chart"}
            </button>
          </div>
        </div>

        <BacktestChart
          priceData={alignedPriceData}
          equityData={alignedEquityData}
          rsiBuyLevel={rsiBuyLevel}
          rsiSellLevel={rsiSellLevel}
        />
      </div>

      {/* Batch backtest / optimizer */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-4 space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm font-semibold">Batch backtest / optimizer</div>
            <div className="text-[11px] text-slate-400">
              Define param grid overrides and run multiple backtests (no auto-refresh).
            </div>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={handleBatchRun}
              className="px-3 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-xs"
            >
              Run batch backtest
            </button>
            <button
              type="button"
              onClick={handleBatchRefresh}
              className="px-3 py-2 rounded-lg border border-slate-700 hover:bg-slate-800 text-xs"
            >
              Refresh results
            </button>
          </div>
        </div>

        <div className="grid md:grid-cols-[2fr,1fr] gap-3">
          <div className="space-y-2">
            {paramGridRows.map((row, idx) => (
              <div key={idx} className="flex gap-2 text-sm">
                <input
                  value={row.name}
                  onChange={(e) =>
                    setParamGridRows((rows) =>
                      rows.map((r, i) => (i === idx ? { ...r, name: e.target.value } : r))
                    )
                  }
                  placeholder="param name"
                  className="w-1/3 bg-slate-950 border border-slate-800 rounded-xl p-2"
                />
                <input
                  value={row.values}
                  onChange={(e) =>
                    setParamGridRows((rows) =>
                      rows.map((r, i) => (i === idx ? { ...r, values: e.target.value } : r))
                    )
                  }
                  placeholder="values (comma-separated numbers)"
                  className="flex-1 bg-slate-950 border border-slate-800 rounded-xl p-2"
                />
                <button
                  type="button"
                  onClick={() =>
                    setParamGridRows((rows) => rows.filter((_, i) => i !== idx))
                  }
                  className="px-2 rounded-lg border border-rose-900 text-rose-200 hover:bg-rose-950"
                >
                  ✕
                </button>
              </div>
            ))}
            <button
              type="button"
              onClick={() => setParamGridRows((rows) => [...rows, { name: "", values: "" }])}
              className="px-3 py-2 rounded-lg border border-slate-700 hover:bg-slate-800 text-xs"
            >
              Add param
            </button>
          </div>

          <div className="space-y-2 text-sm">
            <label className="block">
              <span className="text-xs text-slate-400">Batch label (optional)</span>
              <input
                value={batchLabel}
                onChange={(e) => setBatchLabel(e.target.value)}
                className="mt-1 w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm"
              />
            </label>
            <label className="block">
              <span className="text-xs text-slate-400">Batch ID</span>
              <input
                value={batchId}
                onChange={(e) => setBatchId(e.target.value)}
                className="mt-1 w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm"
                placeholder="from latest run or enter manually"
              />
            </label>
            <div className="flex flex-wrap gap-2 text-xs items-center">
              <label className="flex items-center gap-1">
                <span>Sort by</span>
                <select
                  value={sortField}
                  onChange={(e) => setSortField(e.target.value)}
                  className="bg-slate-950 border border-slate-800 rounded-lg p-1"
                >
                  <option value="sharpe_ratio">Sharpe ratio</option>
                  <option value="return_pct">Return % (sort)</option>
                  <option value="max_drawdown_pct">Max drawdown % (sort)</option>
                  <option value="num_trades">Number of trades</option>
                </select>
              </label>
              <label className="flex items-center gap-1">
                <span>Direction</span>
                <select
                  value={sortDir}
                  onChange={(e) => setSortDir(e.target.value)}
                  className="bg-slate-950 border border-slate-800 rounded-lg p-1"
                >
                  <option value="desc">Descending</option>
                  <option value="asc">Ascending</option>
                </select>
              </label>
              <label className="flex items-center gap-1">
                <span>Min trades</span>
                <input
                  type="number"
                  min={0}
                  value={minTrades}
                  onChange={(e) => setMinTrades(Number(e.target.value))}
                  className="w-20 bg-slate-950 border border-slate-800 rounded-lg p-1"
                />
              </label>
            </div>
            {batchStatus && (
              <div className="text-xs text-slate-300">Status: {batchStatus}</div>
            )}
            {batchError && (
              <div className="text-xs text-rose-300">Batch error: {batchError}</div>
            )}
          </div>
        </div>

        {sortedRuns.best ? (
          <div className="text-xs text-emerald-200 bg-emerald-500/10 border border-emerald-600/40 rounded-xl p-3">
            <div className="font-semibold mb-1">Best config (filtered)</div>
            <div>
              {Object.entries(sortedRuns.best.params || {})
                .map(([k, v]) => `${k}=${v}`)
                .join(", ")}
            </div>
            <div className="flex gap-3 mt-1">
              <span>Sharpe: {sortedRuns.best.stats?.sharpe_ratio ?? "-"}</span>
              <span>Return %: {sortedRuns.best.stats?.return_pct ?? sortedRuns.best.stats?.total_return ?? "-"}</span>
              <span>Max DD %: {sortedRuns.best.stats?.max_drawdown_pct ?? sortedRuns.best.stats?.max_drawdown ?? "-"}</span>
              <span>Trades: {sortedRuns.best.stats?.num_trades ?? "-"}</span>
            </div>
          </div>
        ) : (
          <div className="text-xs text-slate-400">
            No completed runs match the current filters.
          </div>
        )}

        {batchRuns.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="text-slate-400 border-b border-slate-800">
                <tr className="text-left">
                  <th className="py-2 pr-2">Index</th>
                  <th className="py-2 pr-2">Params</th>
                  <th className="py-2 pr-2">Status</th>
                  <th className="py-2 pr-2">Return %</th>
                  <th className="py-2 pr-2">Max DD %</th>
                  <th className="py-2 pr-2">Sharpe</th>
                  <th className="py-2 pr-2">Error</th>
                  <th className="py-2 pr-2 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {batchRuns.map((run) => {
                  const isBest = sortedRuns.best && run.index === sortedRuns.best.index;
                  return (
                    <tr
                      key={run.index}
                      className={`border-t border-slate-900 ${isBest ? "bg-emerald-500/5" : ""}`}
                    >
                      <td className="py-1.5 pr-2">
                        {run.index}
                        {isBest && (
                          <span className="ml-2 px-2 py-0.5 text-[10px] rounded-full border border-emerald-500 text-emerald-200">
                            Best
                          </span>
                        )}
                      </td>
                      <td className="py-1.5 pr-2 whitespace-pre">
                        {JSON.stringify(run.params || {})}
                      </td>
                      <td className="py-1.5 pr-2">{run.status}</td>
                      <td className="py-1.5 pr-2">
                        {run.stats?.return_pct != null
                          ? run.stats.return_pct
                          : run.stats?.total_return}
                      </td>
                      <td className="py-1.5 pr-2">
                        {run.stats?.max_drawdown_pct != null
                          ? run.stats.max_drawdown_pct
                          : run.stats?.max_drawdown}
                      </td>
                      <td className="py-1.5 pr-2">{run.stats?.sharpe_ratio}</td>
                      <td className="py-1.5 pr-2 text-rose-300">{run.error || "-"}</td>
                      <td className="py-1.5 pr-2 text-right">
                        {run.status === "completed" && run.stats ? (
                          <button
                            type="button"
                            className="btn-secondary text-xs"
                            onClick={() =>
                              setPromoteModal({
                                open: true,
                                run,
                                name: "",
                                mode: "paper",
                                saving: false,
                                error: "",
                              })
                            }
                          >
                            Create Bot
                          </button>
                        ) : (
                          "-"
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {promoteModal.open && promoteModal.run && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-slate-950 border border-slate-800 rounded-2xl p-4 w-full max-w-lg space-y-3">
            <div className="text-lg font-semibold">
              Create Bot from run #{promoteModal.run.index}
            </div>
            <div className="text-xs text-slate-300">
              Params:{" "}
              {Object.entries(promoteModal.run.params || {})
                .map(([k, v]) => `${k}=${v}`)
                .join(", ")}
            </div>
            <div className="text-xs text-slate-300">
              Stats: Sharpe {promoteModal.run.stats?.sharpe_ratio ?? "-"} · Return %
              {promoteModal.run.stats?.return_pct ??
                promoteModal.run.stats?.total_return ??
                "-"}{" "}
              · Max DD %
              {promoteModal.run.stats?.max_drawdown_pct ??
                promoteModal.run.stats?.max_drawdown ??
                "-"}{" "}
              · Trades {promoteModal.run.stats?.num_trades ?? "-"}
            </div>
            <label className="block text-sm">
              <span className="text-xs text-slate-400">Bot name</span>
              <input
                value={promoteModal.name}
                onChange={(e) =>
                  setPromoteModal((m) => ({ ...m, name: e.target.value }))
                }
                className="mt-1 w-full bg-slate-900 border border-slate-800 rounded-xl p-2 text-sm"
                placeholder="Bot name"
              />
            </label>
            <label className="block text-sm">
              <span className="text-xs text-slate-400">Mode</span>
              <select
                value={promoteModal.mode}
                onChange={(e) =>
                  setPromoteModal((m) => ({ ...m, mode: e.target.value }))
                }
                className="mt-1 w-full bg-slate-900 border border-slate-800 rounded-xl p-2 text-sm"
              >
                <option value="paper">paper</option>
                <option value="backtest">backtest</option>
                <option value="live">live</option>
              </select>
            </label>
            {promoteModal.error && (
              <div className="text-xs text-rose-300">{promoteModal.error}</div>
            )}
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() =>
                  setPromoteModal({
                    open: false,
                    run: null,
                    name: "",
                    mode: "paper",
                    saving: false,
                    error: "",
                  })
                }
                className="btn-secondary"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={promoteModal.saving}
                onClick={() => promoteRunToBot(promoteModal.run)}
                className="btn-primary disabled:opacity-50"
              >
                {promoteModal.saving ? "Creating..." : "Create Bot"}
              </button>
            </div>
          </div>
        </div>
      )}

      {trades.length > 0 && <BacktestOrdersTable orders={trades} />}

      {singleBotModal.open && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-slate-950 border border-slate-800 rounded-2xl p-4 w-full max-w-lg space-y-3">
            <div className="text-lg font-semibold">Create Bot from backtest</div>
            <div className="text-xs text-slate-400">
              Uses the current strategy JSON and Bot Config values.
            </div>
            <label className="block text-sm">
              <span className="text-xs text-slate-400">Bot name</span>
              <input
                value={singleBotModal.name}
                onChange={(e) =>
                  setSingleBotModal((m) => ({ ...m, name: e.target.value }))
                }
                className="mt-1 w-full bg-slate-900 border border-slate-800 rounded-xl p-2 text-sm"
                placeholder="Bot name"
              />
            </label>
            <label className="block text-sm">
              <span className="text-xs text-slate-400">Mode</span>
              <select
                value={singleBotModal.mode}
                onChange={(e) =>
                  setSingleBotModal((m) => ({ ...m, mode: e.target.value }))
                }
                className="mt-1 w-full bg-slate-900 border border-slate-800 rounded-xl p-2 text-sm"
              >
                <option value="paper">paper</option>
                <option value="backtest">backtest</option>
                <option value="live">live</option>
              </select>
            </label>
            {singleBotModal.error && (
              <div className="text-xs text-rose-300">{singleBotModal.error}</div>
            )}
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() =>
                  setSingleBotModal({
                    open: false,
                    name: "",
                    mode: "paper",
                    saving: false,
                    error: "",
                  })
                }
                className="btn-secondary"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={singleBotModal.saving}
                onClick={createBotFromResult}
                className="btn-primary disabled:opacity-50"
              >
                {singleBotModal.saving ? "Creating..." : "Create Bot"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
