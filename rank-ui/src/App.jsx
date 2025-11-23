// ==============================
// File: src/App.jsx
// ==============================

import { useEffect, useMemo, useState } from "react";
import { useAuth } from "./AuthProvider.jsx";
import Login from "./Login.jsx";
import TradingViewChart from "./TradingViewChart.jsx";
import Navbar from "./components/Navbar.jsx";
import Watchlists from "./pages/Watchlists.jsx";
import Alerts from "./pages/Alerts.jsx";
import Settings from "./pages/Settings.jsx";
import StrategyBuilder from "./pages/StrategyBuilder.jsx";
import Orders from "./pages/Orders.jsx";
import Positions from "./pages/Positions.jsx";
import Performance from "./pages/Performance.jsx";
import Leaderboards from "./pages/Leaderboards.jsx";
import Sparkline from "./components/Sparkline.jsx";
import { APP_NAME } from "./brand";
import StrategyBacktestPage from "./pages/StrategyBacktestPage.jsx";
import Landing from "./Landing.jsx";  // <-- NEW

// [NOTE-CONFIG] If you add a Vite proxy, set BASE = "" and call "/api/...".
const BASE = "http://127.0.0.1:8000";

// [NOTE-API-HELPER] Centralized fetch wrapper with JWT.
async function apiFetch(path, { token, ...opts }) {
  const headers = { ...(opts.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${BASE}${path}`, { ...opts, headers });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(JSON.stringify(json || { status: res.status }));
  return json;
}

// [NOTE-DEFAULTS]
const DEFAULT_TICKERS = "AAPL,MSFT,NVDA,TSLA,AMD";
const DEFAULT_TA = {
  trend: 0.35,
  momentum: 0.25,
  volume: 0.2,
  volatility: 0.1,
  meanreversion: 0.1,
};

const SCREEN_CHOICES = [
  "aggressive_small_caps",
  "conservative_foreign_funds",
  "day_gainers",
  "day_losers",
  "growth_technology_stocks",
  "high_yield_bond",
  "most_actives",
  "most_shorted_stocks",
  "portfolio_anchors",
  "small_cap_gainers",
  "top_mutual_funds",
  "undervalued_growth_stocks",
  "undervalued_large_caps",
];

function IndicatorCell({
  value,
  delta,
  precision = 0,
  deltaPrecision = 1,
}) {
  const isNumber = typeof value === "number";
  const formattedValue = isNumber ? Number(value).toFixed(precision) : value ?? "-";
  const showDelta = typeof delta === "number" && delta !== 0;
  return (
    <div className="flex items-center gap-1">
      <span>{formattedValue}</span>
      {showDelta && (
        <span
          className={`text-xs ${
            delta > 0 ? "text-emerald-400" : "text-rose-400"
          }`}
        >
          {delta > 0 ? "+" : ""}
          {delta.toFixed(deltaPrecision)}
        </span>
      )}
    </div>
  );
}

export default function App() {
  const { token, user, logout } = useAuth();

  // [NOTE-AUTH-GATE]
  if (!token) return <Landing />;

  // -------------------
  // [NOTE-NAV-STATE]
  // -------------------
  const [page, setPage] = useState("dashboard"); // "dashboard" | "watchlists" | "alerts" | "settings"

  // -------------------
  // [NOTE-STATE]
  // -------------------
  const [sparkPeriod, setSparkPeriod] = useState("1M"); // "1W" | "1M" | "3M"
  const [saveOpen, setSaveOpen] = useState(false);
  const [listsForSave, setListsForSave] = useState([]);
  const [saveMode, setSaveMode] = useState("existing"); // "existing" | "new"
  const [saveListId, setSaveListId] = useState(null);
  const [saveListName, setSaveListName] = useState("");
  const [sparkMap, setSparkMap] = useState({}); // { AAPL: [closes...] }
  const [watchlistOptions, setWatchlistOptions] = useState([]);
  const [screenCache, setScreenCache] = useState({});
  const [screenLoading, setScreenLoading] = useState(false);
  const [screenErr, setScreenErr] = useState("");

  const [tickers, setTickers] = useState(
    localStorage.getItem("tickers") || DEFAULT_TICKERS
  );
  const [techWeight, setTechWeight] = useState(
    Number(localStorage.getItem("techWeight") || 0.6)
  );
  const [fundWeight, setFundWeight] = useState(
    Number(localStorage.getItem("fundWeight") || 0.4)
  );
  const [ta, setTa] = useState(() => {
    const saved = localStorage.getItem("taWeights");
    return saved ? JSON.parse(saved) : DEFAULT_TA;
  });
  // [NOTE-ONBOARDING]
  const [showOnboarding, setShowOnboarding] = useState(() => {
    // default: show if we've never set the flag
    return localStorage.getItem("seenOnboarding") !== "1";
  });

  const [loading, setLoading] = useState(false);
  const [rows, setRows] = useState([]);
  const [errors, setErrors] = useState([]);
  const [explain, setExplain] = useState(null);
  const [chartSym, setChartSym] = useState(null);
  const [yfCount, setYfCount] = useState(null);
  // [NOTE-QUICK-ALERT-STATE]
  const [quickAlertSym, setQuickAlertSym] = useState(null);
  const [quickAlertFinal, setQuickAlertFinal] = useState(null);
  const [quickAlertMinFinal, setQuickAlertMinFinal] = useState("");
  const [quickAlertTriggerOnce, setQuickAlertTriggerOnce] = useState(true);
  const [quickAlertErr, setQuickAlertErr] = useState("");

  const [errMsg, setErrMsg] = useState("");

  // [NOTE-PERSIST]
  useEffect(() => {
    localStorage.setItem("tickers", tickers);
    localStorage.setItem("techWeight", String(techWeight));
    localStorage.setItem("fundWeight", String(fundWeight));
    localStorage.setItem("taWeights", JSON.stringify(ta));
  }, [tickers, techWeight, fundWeight, ta]);

  useEffect(() => {
    if (!token || !import.meta.env.DEV) return undefined;
    let active = true;

    async function fetchYFinanceCount() {
      try {
        const res = await apiFetch("/api/metrics/yfinance/", { token });
        if (active) setYfCount(res.count);
      } catch (e) {
        if (active) setYfCount(null);
      }
    }

    fetchYFinanceCount();
    const intervalId = setInterval(fetchYFinanceCount, 10000);
    return () => {
      active = false;
      clearInterval(intervalId);
    };
  }, [token]);


  // [NOTE-BODY FOR RANK]
  const body = useMemo(
    () => ({
      tickers: tickers
        .split(",")
        .map((s) => s.trim().toUpperCase())
        .filter(Boolean),
      tech_weight: techWeight,
      fund_weight: fundWeight,
      ta_weights: ta,
    }),
    [tickers, techWeight, fundWeight, ta]
  );

  function getSparkParams(periodKey) {
    switch (periodKey) {
      case "1W":
        return { period: "7d", interval: "1d" };
      case "3M":
        return { period: "3mo", interval: "1d" };
      case "1M":
      default:
        return { period: "1mo", interval: "1d" };
    }
  }

  async function fetchSparklinesForRows(rowList) {
    const syms = (rowList || []).map((r) => r.symbol).join(",");
    if (!syms) {
      setSparkMap({});
      return;
    }
    const { period, interval } = getSparkParams(sparkPeriod);
    try {
      const sres = await apiFetch(
        `/api/sparkline?symbols=${encodeURIComponent(
          syms
        )}&period=${encodeURIComponent(period)}&interval=${encodeURIComponent(
          interval
        )}`,
        { token }
      );
      const map = {};
      (sres.results || []).forEach((r) => {
        map[r.symbol] = r.closes || [];
      });
      setSparkMap(map);
    } catch {
      // non-fatal
    }
  }

  // [NOTE-ACTIONS] Rank
  async function rank() {
    setLoading(true);
    setErrors([]);
    setErrMsg("");

    try {
      const json = await apiFetch(`/api/rank`, {
        token,
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      const results = json.results || [];
      setRows(results);
      setErrors(json.errors || []);

      await fetchSparklinesForRows(results);
    } catch (e) {
      setErrMsg(String(e));
    } finally {
      setLoading(false);
    }
  }

  // [NOTE-WATCHLISTS-FOR-SAVE] load into modal
  async function fetchWatchlistsForSave() {
    try {
      const data = await apiFetch("/api/watchlists/", { token });
      const list = Array.isArray(data) ? data : data.results || [];
      setListsForSave(list);
      setWatchlistOptions(list);
      if (!saveListId && list.length) {
        setSaveListId(list[0].id);
      }
    } catch {
      // ignore
    }
  }
  useEffect(() => {
    localStorage.setItem("seenOnboarding", showOnboarding ? "0" : "1");
  }, [showOnboarding]);

  useEffect(() => {
    if (saveOpen) {
      fetchWatchlistsForSave();
    }
  }, [saveOpen]);

  useEffect(() => {
    if (token) {
      fetchWatchlistsForSave();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  // refetch sparklines when period changes
  useEffect(() => {
    if (rows.length) {
      fetchSparklinesForRows(rows);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sparkPeriod]);

  function applyTickerList(symbols) {
    if (!Array.isArray(symbols) || !symbols.length) return;
    setTickers(symbols.join(", "));
  }

  function handleWatchlistSelect(e) {
    const val = e.target.value;
    if (!val) return;
    const selected = watchlistOptions.find((wl) => String(wl.id) === val);
    if (selected && Array.isArray(selected.items)) {
      applyTickerList(selected.items.map((item) => item.symbol).filter(Boolean));
    }
    e.target.value = "";
  }

  async function handleScreenSelect(e) {
    const screen = e.target.value;
    if (!screen) return;
    setScreenErr("");
    if (screenCache[screen]?.length) {
      applyTickerList(screenCache[screen]);
      e.target.value = "";
      return;
    }
    setScreenLoading(true);
    try {
      const data = await apiFetch(
        `/api/default-tickers/aggressive-small-caps/?screen=${encodeURIComponent(
          screen
        )}`,
        { token }
      );
      const symbols = data?.symbols || [];
      setScreenCache((prev) => ({ ...prev, [screen]: symbols }));
      applyTickerList(symbols);
    } catch (err) {
      setScreenErr(err.message || String(err));
    } finally {
      setScreenLoading(false);
      e.target.value = "";
    }
  }
  // [NOTE-QUICK-ALERT-ACTION]
  async function createQuickAlert() {
    if (!quickAlertSym) return;
    setQuickAlertErr("");

    try {
      const payload = {
        alert_type: "symbol",
        symbol: quickAlertSym,
        min_final_score: Number(quickAlertMinFinal) || 0,
        min_tech_score: null,
        min_fund_score: null,
        trigger_once: quickAlertTriggerOnce,
        active: true,
      };

      await apiFetch(`/api/alerts/`, {
        token,
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      // Close modal on success
      setQuickAlertSym(null);
    } catch (e) {
      setQuickAlertErr(e.message || String(e));
    }
  }

  // [NOTE-ACTIONS] Explain
  async function openExplain(symbol) {
    setErrMsg("");
    try {
      const params = new URLSearchParams({
        symbol,
        refresh: "true",
        tech_weight: String(techWeight),
        fund_weight: String(fundWeight),
        ta_trend: String(ta.trend),
        ta_momentum: String(ta.momentum),
        ta_volume: String(ta.volume),
        ta_volatility: String(ta.volatility),
        ta_meanreversion: String(ta.meanreversion),
      });
      const json = await apiFetch(`/api/explain?${params.toString()}`, {
        token,
      });
      setExplain(json);
    } catch (e) {
      setErrMsg(String(e));
    }
  }

  // [NOTE-ACTIONS] Save current tickers into a watchlist
  async function saveCurrentTickers() {
    try {
      let targetId = saveListId;

      // Create new list if needed
      if (saveMode === "new") {
        if (!saveListName.trim()) return;
        const created = await apiFetch(`/api/watchlists/`, {
          token,
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: saveListName.trim() }),
        });
        targetId = created.id;
      }

      const symbols = body.tickers;
      for (const sym of symbols) {
        await apiFetch(`/api/watchlists/${targetId}/items/`, {
          token,
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ symbol: sym }),
        }).catch(() => {
          // ignore duplicates
        });
      }

      setSaveOpen(false);
    } catch (e) {
      setErrMsg(String(e));
    }
  }

  function number(n, d = 2) {
    return typeof n === "number" ? n.toFixed(d) : n;
  }

  // ==============================
  // [NOTE-UI] App Shell
  // ==============================
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      {/* NAVBAR */}
      <Navbar
        user={user}
        onLogout={logout}
        active={page}
        onNavigate={setPage}
        yfCount={yfCount}
        showYfCounter={import.meta.env.DEV}
      />

      <main className="max-w-7xl mx-auto p-6 space-y-6">
        {/* ==============================
          DASHBOARD PAGE
         ============================== */}
        {page === "dashboard" && (
          <>
            {/* [NOTE-ONBOARDING-PANEL] */}
            {showOnboarding && (
              <div className="bg-indigo-950/40 border border-indigo-700/60 rounded-2xl p-4 flex flex-col sm:flex-row sm:items-start gap-4">
                <div className="flex-1">
                  <div className="text-sm font-semibold mb-1">
                    Welcome to Stock Ranker
                  </div>
                  <p className="text-xs text-slate-300 mb-2">
                    Here’s a quick path to get useful output in under a minute:
                  </p>
                  <ol className="list-decimal ml-4 space-y-1 text-xs text-slate-200">
                    <li>Enter a basket of tickers you care about.</li>
                    <li>Adjust tech vs fund weights and TA sub-weights.</li>
                    <li>
                      Click <span className="font-semibold">Rank</span> to score
                      the basket.
                    </li>
                    <li>
                      Use <span className="font-semibold">Chart</span> and{" "}
                      <span className="font-semibold">Explain</span> on
                      interesting names.
                    </li>
                    <li>
                      Save a watchlist or set{" "}
                      <span className="font-semibold">Alerts</span> so you get an
                      email when scores move.
                    </li>
                    <li>
                      Try the{" "}
                      <span className="font-semibold">
                        Strategy Backtest (Exp)
                      </span>{" "}
                      tab to validate JSON specs and run explicit backtests.
                    </li>
                  </ol>
                </div>
                <div className="flex flex-col gap-2 text-xs">
                  <button
                    onClick={() => setShowOnboarding(false)}
                    className="px-3 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white"
                  >
                    Got it, hide this
                  </button>
                  <button
                    onClick={() => {
                      setShowOnboarding(false);
                      rank();
                    }}
                    className="px-3 py-1.5 rounded-xl border border-slate-700 hover:bg-slate-900"
                  >
                    Run a first rank
                  </button>
                </div>
              </div>
            )}

            {/* === your existing Dashboard CTA + controls + table === */}

            {/* CTA card */}
            <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-4 flex items-center justify-between">
              <div>
                <div className="text-lg font-semibold">{APP_NAME} Dashboard</div>
                <div className="text-sm text-slate-400">
                  Tune weights • Rank basket • Inspect components
                </div>
              </div>
              <button
                onClick={rank}
                disabled={loading}
                className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-60 shadow"
              >
                {loading ? "Ranking..." : "Rank"}
              </button>
            </div>

            {/* Controls */}
            <section className="grid lg:grid-cols-2 gap-4">
              <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-4 space-y-2">
                <label className="block text-sm mb-1">
                  Tickers (comma-separated)
                </label>
                <input
                  value={tickers}
                  onChange={(e) => setTickers(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  placeholder="AAPL, MSFT, NVDA, TSLA, AMD"
                />
                <div className="flex flex-col gap-2">
                  <select
                    defaultValue=""
                    onChange={handleWatchlistSelect}
                    className="bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm"
                  >
                    <option value="">Load one of your watchlists…</option>
                    {watchlistOptions.map((wl) => (
                      <option key={wl.id} value={wl.id}>
                        {wl.name} ({(wl.items || []).length})
                      </option>
                    ))}
                  </select>
                  <select
                    defaultValue=""
                    onChange={handleScreenSelect}
                    disabled={screenLoading}
                    className="bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm disabled:opacity-60"
                  >
                    <option value="">
                      {screenLoading
                        ? "Loading screen..."
                        : "Load a Yahoo Finance screen…"}
                    </option>
                    {SCREEN_CHOICES.map((screen) => (
                      <option key={screen} value={screen}>
                        {screen.replace(/_/g, " ")}
                      </option>
                    ))}
                  </select>
                </div>
                {screenErr && (
                  <p className="text-xs text-rose-400">{screenErr}</p>
                )}
                <div className="grid grid-cols-2 gap-3 mt-4">
                  <NumberInput
                    label="Tech weight"
                    value={techWeight}
                    setValue={setTechWeight}
                    step={0.05}
                  />
                  <NumberInput
                    label="Fund weight"
                    value={fundWeight}
                    setValue={setFundWeight}
                    step={0.05}
                  />
                </div>
                <p className="text-xs text-slate-500 mt-2">
                  Weights don’t need to sum to 1; they’re multipliers.
                </p>
              </div>

              <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-4">
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  {["trend", "momentum", "volume", "volatility", "meanreversion"].map(
                    (k) => (
                      <NumberInput
                        key={k}
                        label={`TA ${k}`}
                        value={ta[k]}
                        setValue={(v) =>
                          setTa((prev) => ({ ...prev, [k]: v }))
                        }
                        step={0.05}
                      />
                    )
                  )}
                </div>
                <p className="text-xs text-slate-500 mt-2">
                  TA sub-weights apply inside the technical score.
                </p>
              </div>
            </section>

            {/* Errors */}
            {!!errMsg && (
              <div className="bg-rose-950/50 text-rose-200 border border-rose-900 p-3 rounded-xl">
                <div className="font-semibold">Request Error</div>
                <pre className="text-sm whitespace-pre-wrap break-words">
                  {errMsg}
                </pre>
              </div>
            )}
            {!!errors.length && (
              <div className="bg-amber-950/40 text-amber-200 border border-amber-800 p-3 rounded-xl">
                <div className="font-semibold mb-1">Server Errors</div>
                <ul className="list-disc pl-5">
                  {errors.map((e, i) => (
                    <li key={i}>
                      [{e.symbol}] {e.error}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Results table + sparkline period toggle */}
            <section className="bg-slate-900/50 border border-slate-800 rounded-2xl p-4 overflow-auto">
              <div className="flex items-center justify-between mb-2">
                <div className="text-sm font-semibold text-slate-300">
                  Results
                </div>
                <div className="flex items-center gap-2 text-xs">
                  <span className="text-slate-500">Spark period:</span>
                  {["1W", "1M", "3M"].map((p) => (
                    <button
                      key={p}
                      onClick={() => setSparkPeriod(p)}
                      className={`px-2 py-1 rounded-full border text-xs ${sparkPeriod === p
                        ? "bg-indigo-600 border-indigo-500 text-white"
                        : "bg-slate-900 border-slate-700 text-slate-300 hover:bg-slate-800"
                        }`}
                    >
                      {p}
                    </button>
                  ))}
                </div>
              </div>

              <table className="w-full text-sm">
                <thead className="text-slate-400">
                  <tr className="text-left">
                    <Th>Symbol</Th>
                    <Th>Spark</Th>
                    <Th>Tech</Th>
                    <Th>Fund</Th>
                    <Th>Final</Th>
                    <Th>Trend</Th>
                    <Th>Momo</Th>
                    <Th>Vol</Th>
                    <Th>MeanRev</Th>
                    <Th></Th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => {
                    const t = r.components?.technical || {};
                    const deltas = r.technical_deltas || {};
                    return (
                      <tr
                        key={r.symbol}
                        className="border-t border-slate-800"
                      >
                        <Td className="font-semibold">{r.symbol}</Td>
                        <Td>
                          <Sparkline data={sparkMap[r.symbol]} />
                        </Td>
                        <Td>
                          <IndicatorCell
                            value={
                              typeof r.tech_score === "number"
                                ? r.tech_score
                                : Number(r.tech_score)
                            }
                            delta={r.tech_score_delta}
                            precision={1}
                            deltaPrecision={1}
                          />
                        </Td>
                        <Td>{number(r.fundamental_score)}</Td>
                        <Td>
                          <ScorePill value={number(r.final_score)} />
                        </Td>
                        <Td>
                          <IndicatorCell
                            value={t.trend_raw}
                            delta={deltas.trend_raw}
                          />
                        </Td>
                        <Td>
                          <IndicatorCell
                            value={t.momentum_raw}
                            delta={deltas.momentum_raw}
                          />
                        </Td>
                        <Td>
                          <IndicatorCell
                            value={t.volume_raw}
                            delta={deltas.volume_raw}
                          />
                        </Td>
                        <Td>
                          <IndicatorCell
                            value={t.meanreversion_raw}
                            delta={deltas.meanreversion_raw}
                          />
                        </Td>
                        <Td className="text-right">
                          <div className="inline-flex gap-2">
                            <button
                              onClick={() => openExplain(r.symbol)}
                              className="px-3 py-1 rounded-lg border border-slate-700 hover:bg-slate-800"
                            >
                              Explain
                            </button>
                            <button
                              onClick={() => setChartSym(r.symbol)}
                              className="px-3 py-1 rounded-lg border border-slate-700 hover:bg-slate-800"
                              title="Open chart"
                            >
                              Chart
                            </button>
                            <button
                              onClick={() =>
                                openQuickAlert(r.symbol, r.final_score)
                              }
                              className="px-3 py-1 rounded-lg border border-emerald-700 text-emerald-200 hover:bg-emerald-950 text-xs"
                            >
                              Alert
                            </button>
                          </div>
                        </Td>
                      </tr>
                    );
                  })}
                  {!rows.length && !loading && (
                    <tr>
                      <td
                        className="py-6 text-center text-slate-500"
                        colSpan={10}
                      >
                        No data yet. Click “Rank”.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </section>

            <footer className="pt-2 text-xs text-slate-500">
              © {new Date().getFullYear()} {APP_NAME}. All rights reserved.
            </footer>
          </>
        )}

        {/* ==============================
          OTHER PAGES
         ============================== */}
        {page === "watchlists" && (
          <Watchlists
            onUseTickers={(symbols) => {
              setTickers(symbols.join(","));
              setPage("dashboard");
            }}
          />
        )}

        {page === "alerts" && <Alerts />}

        {page === "strategy-backtest" && <StrategyBacktestPage />}

        {page === "orders" && <Orders />}

        {page === "positions" && <Positions />}

        {page === "performance" && <Performance />}

        {page === "leaderboards" && <Leaderboards />}

        {page === "settings" && (
          <Settings
            tickers={tickers}
            techWeight={techWeight}
            fundWeight={fundWeight}
            ta={ta}
            setTickers={setTickers}
            setTechWeight={setTechWeight}
            setFundWeight={setFundWeight}
            setTa={setTa}
          />
        )}

        {page === "strategies" && <StrategyBuilder />}
      </main>

      {/* ==============================
        SAVE-TO-WATCHLIST MODAL
       ============================== */}
      {saveOpen && (
        <div
          className="fixed inset-0 bg-black/40 flex items-end sm:items-center sm:justify-center"
          onClick={() => setSaveOpen(false)}
        >
          <div
            className="w-full sm:max-w-md bg-slate-950 border border-slate-800 rounded-2xl p-4 m-2"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-lg font-bold">Save current tickers</h2>
              <button
                onClick={() => setSaveOpen(false)}
                className="text-slate-400 hover:text-white"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3 text-sm">
              <div className="text-slate-400">
                {body.tickers.join(", ")}
              </div>

              <div className="flex gap-3">
                <label className="inline-flex items-center gap-2">
                  <input
                    type="radio"
                    name="savemode"
                    value="existing"
                    checked={saveMode === "existing"}
                    onChange={() => setSaveMode("existing")}
                  />
                  Existing list
                </label>
                <label className="inline-flex items-center gap-2">
                  <input
                    type="radio"
                    name="savemode"
                    value="new"
                    checked={saveMode === "new"}
                    onChange={() => setSaveMode("new")}
                  />
                  New list
                </label>
              </div>

              {saveMode === "existing" ? (
                <select
                  value={saveListId || ""}
                  onChange={(e) => setSaveListId(Number(e.target.value))}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2"
                >
                  {listsForSave.map((l) => (
                    <option key={l.id} value={l.id}>
                      {l.name}
                    </option>
                  ))}
                  {!listsForSave.length && (
                    <option value="">No lists yet</option>
                  )}
                </select>
              ) : (
                <input
                  value={saveListName}
                  onChange={(e) => setSaveListName(e.target.value)}
                  placeholder="New watchlist name"
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2"
                />
              )}

              <div className="flex justify-end gap-2 pt-2">
                <button
                  onClick={() => setSaveOpen(false)}
                  className="px-3 py-2 rounded-xl border border-slate-700 hover:bg-slate-900"
                >
                  Cancel
                </button>
                <button
                  onClick={saveCurrentTickers}
                  className="px-3 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500"
                >
                  Save
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* QUICK ALERT MODAL */}
      {quickAlertSym && (
        <div
          className="fixed inset-0 bg-black/40 flex items-center justify-center z-40"
          onClick={() => setQuickAlertSym(null)}
        >
          <div
            className="w-full max-w-sm bg-slate-950 border border-slate-800 rounded-2xl p-4 m-2"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-lg font-bold">
                Create alert for {quickAlertSym}
              </h2>
              <button
                onClick={() => setQuickAlertSym(null)}
                className="text-slate-400 hover:text-white"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3 text-sm">
              {quickAlertFinal != null && (
                <div className="text-xs text-slate-400">
                  Current final score:{" "}
                  <span className="text-slate-100 font-semibold">
                    {Number(quickAlertFinal).toFixed(2)}
                  </span>
                </div>
              )}

              <div>
                <label className="block text-xs text-slate-400 mb-1">
                  Alert when final score ≥
                </label>
                <input
                  type="number"
                  value={quickAlertMinFinal}
                  onChange={(e) => setQuickAlertMinFinal(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm"
                />
              </div>

              <label className="inline-flex items-center gap-2 text-xs">
                <input
                  type="checkbox"
                  checked={quickAlertTriggerOnce}
                  onChange={() =>
                    setQuickAlertTriggerOnce((v) => !v)
                  }
                />
                Trigger once (disable after first hit)
              </label>

              {quickAlertErr && (
                <div className="text-xs text-rose-300">
                  {quickAlertErr}
                </div>
              )}

              <div className="flex justify-end gap-2 pt-2">
                <button
                  onClick={() => setQuickAlertSym(null)}
                  className="px-3 py-2 rounded-xl border border-slate-700 hover:bg-slate-900 text-xs"
                >
                  Cancel
                </button>
                <button
                  onClick={createQuickAlert}
                  className="px-3 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-xs"
                >
                  Save alert
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* EXPLAIN DRAWER */}
      {explain && (
        <div
          className="fixed inset-0 bg-black/40 flex justify-end"
          onClick={() => setExplain(null)}
        >
          <div
            className="w-full max-w-2xl h-full bg-slate-950 border-l border-slate-800 p-6 overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold">Explain: {explain.symbol}</h2>
              <button
                onClick={() => setExplain(null)}
                className="text-slate-400 hover:text-white"
              >
                ✕
              </button>
            </div>

            <div className="grid grid-cols-3 gap-3 mb-4">
              <Card title="Tech" value={number(explain.tech_score)} />
              <Card
                title="Fund"
                value={number(explain.fundamental_score)}
              />
              <Card title="Final" value={number(explain.final_score)} />
            </div>

            <Section title="Technical">
              <JSONBlock data={explain.components?.technical} />
            </Section>
            <Section title="Fundamental">
              <JSONBlock data={explain.components?.fundamental} />
            </Section>
            <Section title="Weights">
              <JSONBlock data={explain.components?.weights} />
            </Section>
          </div>
        </div>
      )}

      {/* CHART DRAWER */}
      {chartSym && (
        <div
          className="fixed inset-0 bg-black/40 flex justify-end"
          onClick={() => setChartSym(null)}
        >
          <div
            className="w-full max-w-4xl h-full bg-slate-950 border-l border-slate-800 p-4 overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-xl font-bold">Chart: {chartSym}</h2>
              <button
                onClick={() => setChartSym(null)}
                className="text-slate-400 hover:text-white"
              >
                ✕
              </button>
            </div>

            <div className="rounded-xl overflow-hidden border border-slate-800 h-[78vh]">
              <TradingViewChart
                symbol={chartSym}
                exchangePrefix=""
                interval="D"
                studies={[
                  "RSI@tv-basicstudies",
                  "MACD@tv-basicstudies",
                  "OBV@tv-basicstudies",
                ]}
                autosize={false}
                height={720}
              />
            </div>

            <div className="mt-3 text-slate-400 text-sm">
              Tip: use the chart toolbar to add EMAs/Bollinger Bands and change
              intervals.
            </div>
          </div>
        </div>
      )}
    </div>
  );

  /* ==============================
     Helpers
     ============================== */

  function NumberInput({ label, value, setValue, step = 0.05 }) {
    return (
      <div>
        <label className="block text-sm mb-1">{label}</label>
        <input
          type="number"
          step={step}
          value={value}
          onChange={(e) => setValue(Number(e.target.value))}
          className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
      </div>
    );
  }

  function Th({ children }) {
    return <th className="py-2 font-medium">{children}</th>;
  }

  function Td({ children, className = "" }) {
    return <td className={`py-2 pr-2 ${className}`}>{children}</td>;
  }

  function ScorePill({ value }) {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-slate-800 border border-slate-700">
        {value}
      </span>
    );
  }

  function Card({ title, value }) {
    return (
      <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-3">
        <div className="text-slate-400 text-xs">{title}</div>
        <div className="text-lg font-bold">{value}</div>
      </div>
    );
  }

  function Section({ title, children }) {
    return (
      <div className="mb-4">
        <div className="font-semibold mb-1">{title}</div>
        {children}
      </div>
    );
  }

  function JSONBlock({ data }) {
    return (
      <pre className="bg-slate-900/50 border border-slate-800 rounded-xl p-3 overflow-auto text-xs">
        {JSON.stringify(data ?? {}, null, 2)}
      </pre>
    );
  }
}
