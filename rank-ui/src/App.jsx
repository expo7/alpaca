// ==============================
// File: src/App.jsx
// ==============================

import { useCallback, useEffect, useMemo, useState } from "react";
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
import BotsPage from "./pages/BotsPage.jsx";
import BacktestHistoryPage from "./pages/BacktestHistoryPage.jsx";
import BotDetailPage from "./pages/BotDetailPage.jsx";
import MacroDashboardPage from "./pages/MacroDashboardPage.jsx";
import Landing from "./Landing.jsx";  // <-- NEW
import ArticlesListPage from "./pages/ArticlesListPage.jsx";
import ArticleDetailPage from "./pages/ArticleDetailPage.jsx";
import useQuotes from "./hooks/useQuotes.js";

// [NOTE-CONFIG] If you add a Vite proxy, set BASE = "" and call "/api/...".
const BASE = "";

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

const CHART_STUDIES = [
  "RSI@tv-basicstudies",
  "MACD@tv-basicstudies",
  "OBV@tv-basicstudies",
];

const V1_MODE = true;
const V1_ALLOWED_PAGES = new Set(["dashboard"]);
const MIN_LOADING_MS = 300;
const DEBUG_CHART = false;
const CHART_DEBUG_LIMIT = 24;

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForMinimum(startedAt, minimumMs = MIN_LOADING_MS) {
  const elapsed = Date.now() - startedAt;
  if (elapsed < minimumMs) {
    await sleep(minimumMs - elapsed);
  }
}

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
          className={`text-xs ${delta > 0 ? "text-emerald-400" : "text-rose-400"
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
  const isAuthed = Boolean(token);
  const [pathname, setPathname] = useState(() => window.location.pathname || "/");

  useEffect(() => {
    const onPopState = () => setPathname(window.location.pathname || "/");
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const route = useMemo(() => {
    if (pathname === "/articles") return { kind: "articles-list" };
    if (pathname.startsWith("/articles/")) {
      const slug = decodeURIComponent(pathname.replace(/^\/articles\//, "")).trim();
      if (slug) return { kind: "article-detail", slug };
    }
    return { kind: "app" };
  }, [pathname]);

  const navigatePath = useCallback((nextPath) => {
    if (!nextPath || nextPath === pathname) return;
    window.history.pushState({}, "", nextPath);
    setPathname(nextPath);
  }, [pathname]);

  // -------------------
  // [NOTE-NAV-STATE]
  // -------------------
  const [page, setPage] = useState("dashboard"); // "dashboard" | "watchlists" | "alerts" | "settings"

  const isBlockedPage = useCallback(
    (nextPage) => V1_MODE && !V1_ALLOWED_PAGES.has(nextPage),
    []
  );

  const navigateToPage = useCallback(
    (nextPage) => {
      // Handle articles navigation separately using path routing
      if (nextPage === "articles") {
        navigatePath("/articles");
        return;
      }
      if (isBlockedPage(nextPage)) {
        setPage("dashboard");
        return;
      }
      setPage(nextPage);
    },
    [isBlockedPage, navigatePath]
  );

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
  const [selectedBotId, setSelectedBotId] = useState(null);
  const [watchlistOptions, setWatchlistOptions] = useState([]);
  const [dashboardWatchlist, setDashboardWatchlist] = useState(null);
  const [watchlistInput, setWatchlistInput] = useState("");
  const [watchlistSectionLoading, setWatchlistSectionLoading] = useState(false);
  const [watchlistAddingSymbol, setWatchlistAddingSymbol] = useState("");
  const [watchlistRemovingItemId, setWatchlistRemovingItemId] = useState(null);
  const [watchlistFeedback, setWatchlistFeedback] = useState("");
  const [watchlistSectionErr, setWatchlistSectionErr] = useState("");
  const [recentAlerts, setRecentAlerts] = useState([]);
  const [recentAlertsLoading, setRecentAlertsLoading] = useState(false);
  const [recentAlertsErr, setRecentAlertsErr] = useState("");
  const [latestInsights, setLatestInsights] = useState([]);
  const [latestInsightsLoading, setLatestInsightsLoading] = useState(false);
  const [latestInsightsErr, setLatestInsightsErr] = useState("");
  const [macroSnapshot, setMacroSnapshot] = useState(null);
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
  const [chartDebugEvents, setChartDebugEvents] = useState([]);
  // [NOTE-QUICK-ALERT-STATE]
  const [quickAlertSym, setQuickAlertSym] = useState(null);
  const [quickAlertFinal, setQuickAlertFinal] = useState(null);
  const [quickAlertMinFinal, setQuickAlertMinFinal] = useState("");
  const [quickAlertTriggerOnce, setQuickAlertTriggerOnce] = useState(true);
  const [quickAlertErr, setQuickAlertErr] = useState("");
  const [quickAlertSaving, setQuickAlertSaving] = useState(false);
  const [saveBusy, setSaveBusy] = useState(false);
  const [explainingSymbol, setExplainingSymbol] = useState(null);

  const [errMsg, setErrMsg] = useState("");

  useEffect(() => {
    if (!isAuthed || route.kind !== "app") return;

    let alive = true;

    async function fetchLatestInsights() {
      setLatestInsightsLoading(true);
      setLatestInsightsErr("");
      try {
        const res = await fetch(`${BASE}/api/articles/`);
        const json = await res.json().catch(() => []);
        if (!res.ok) throw new Error(json?.detail || "Failed to load insights.");

        const sorted = (Array.isArray(json) ? json : [])
          .slice()
          .sort((a, b) => {
            const aTime = new Date(a?.created_at || 0).getTime();
            const bTime = new Date(b?.created_at || 0).getTime();
            return bTime - aTime;
          })
          .slice(0, 3);

        if (!alive) return;
        setLatestInsights(sorted);
      } catch (e) {
        if (!alive) return;
        setLatestInsightsErr(e?.message || "Failed to load insights.");
      } finally {
        if (alive) setLatestInsightsLoading(false);
      }
    }

    fetchLatestInsights();
    return () => {
      alive = false;
    };
  }, [isAuthed, route.kind]);

  const pushChartDebug = useCallback((message, meta = {}) => {
    if (!DEBUG_CHART) return;
    const event = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      at: new Date().toISOString(),
      message,
      meta,
    };
    setChartDebugEvents((prev) => [event, ...prev].slice(0, CHART_DEBUG_LIMIT));
    const hasMeta = meta && Object.keys(meta).length > 0;
    if (hasMeta) {
      console.log(`[chart-debug] ${message}`, meta);
      return;
    }
    console.log(`[chart-debug] ${message}`);
  }, []);

  const liveQuotes = useQuotes(rows.map((r) => r.symbol));

  const rankedBySymbol = useMemo(() => {
    const map = new Map();
    rows.forEach((row) => {
      map.set(row.symbol, row);
    });
    return map;
  }, [rows]);

  const watchlistRows = useMemo(() => {
    const items = dashboardWatchlist?.items || [];
    return items.map((item) => {
      const symbol = item.symbol;
      const ranked = rankedBySymbol.get(symbol);
      const delta = ranked?.tech_score_delta;
      let status = "Neutral";
      if (typeof delta === "number" && delta > 0.25) status = "Improving";
      if (typeof delta === "number" && delta < -0.25) status = "Weakening";

      return {
        id: item.id,
        symbol,
        name: item.name || item.company_name || ranked?.name || "",
        rating:
          typeof ranked?.final_score === "number"
            ? Number(ranked.final_score).toFixed(1)
            : "-",
        status,
      };
    });
  }, [dashboardWatchlist, rankedBySymbol]);

  const dashboardAlertRows = useMemo(() => {
    const synthetic = [];
    if (macroSnapshot?.regime) {
      synthetic.push({
        id: "market-direction",
        symbol: null,
        tag: "Market",
        text: `Market direction is ${macroSnapshot.regime}.`,
        timestamp: macroSnapshot.asOf || new Date().toISOString(),
      });
    }

    const topRanked = rows[0];
    if (topRanked && typeof topRanked.final_score === "number") {
      synthetic.push({
        id: `top-ranked-${topRanked.symbol}`,
        symbol: topRanked.symbol,
        tag: "Ranking",
        text: `${topRanked.symbol} moved into the top-ranked names.`,
        timestamp: new Date().toISOString(),
      });
    }

    const watchlistSymbols = new Set((dashboardWatchlist?.items || []).map((it) => it.symbol));
    const apiAlerts = (recentAlerts || []).map((evt) => {
      const symbol = evt.symbol || null;
      const isWatchlist = symbol && watchlistSymbols.has(symbol);
      const tag = isWatchlist ? "Watchlist" : "Alert";
      const rating = typeof evt.final_score === "number" ? evt.final_score.toFixed(1) : null;
      const text = symbol
        ? `${symbol} triggered an alert${rating ? ` at rating ${rating}` : ""}.`
        : "An alert was triggered.";
      return {
        id: `alert-${evt.id}`,
        symbol,
        tag,
        text,
        timestamp: evt.triggered_at,
      };
    });

    const merged = [...synthetic, ...apiAlerts]
      .filter((row) => row.timestamp)
      .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());

    return merged.slice(0, 8);
  }, [dashboardWatchlist, macroSnapshot, recentAlerts, rows]);

  // [NOTE-PERSIST]
  useEffect(() => {
    localStorage.setItem("tickers", tickers);
    localStorage.setItem("techWeight", String(techWeight));
    localStorage.setItem("fundWeight", String(fundWeight));
    localStorage.setItem("taWeights", JSON.stringify(ta));
  }, [tickers, techWeight, fundWeight, ta]);


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
    const startedAt = Date.now();
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
      await waitForMinimum(startedAt);
      setLoading(false);
    }
  }

  // [NOTE-WATCHLISTS-FOR-SAVE] load into modal
  const fetchWatchlistsForSave = useCallback(async () => {
    const startedAt = Date.now();
    try {
      setWatchlistSectionLoading(true);
      setWatchlistSectionErr("");
      const data = await apiFetch("/api/watchlists/", { token });
      const list = Array.isArray(data) ? data : data.results || [];
      setListsForSave(list);
      setWatchlistOptions(list);
      if (!saveListId && list.length) {
        setSaveListId(list[0].id);
      }
      setDashboardWatchlist(list[0] || null);
    } catch {
      setWatchlistSectionErr("Something went wrong. Retry.");
    } finally {
      await waitForMinimum(startedAt);
      setWatchlistSectionLoading(false);
    }
  }, [token, saveListId]);

  const fetchRecentAlerts = useCallback(async () => {
    if (!token) return;
    const startedAt = Date.now();
    try {
      setRecentAlertsLoading(true);
      setRecentAlertsErr("");
      const data = await apiFetch("/api/alert-events/", { token });
      const events = Array.isArray(data) ? data : data.results || [];
      const sorted = [...events].sort((a, b) => {
        const ta = new Date(a.triggered_at || 0).getTime();
        const tb = new Date(b.triggered_at || 0).getTime();
        return tb - ta;
      });
      setRecentAlerts(sorted);
    } catch {
      setRecentAlertsErr("Something went wrong. Retry.");
    } finally {
      await waitForMinimum(startedAt);
      setRecentAlertsLoading(false);
    }
  }, [token]);

  async function ensureDashboardWatchlistId() {
    if (dashboardWatchlist?.id) return dashboardWatchlist.id;
    const created = await apiFetch(`/api/watchlists/`, {
      token,
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: "My Watchlist" }),
    });
    await fetchWatchlistsForSave();
    return created.id;
  }

  async function addTickerToWatchlist(rawSymbol) {
    const symbol = String(rawSymbol || "").trim().toUpperCase();
    if (!symbol) return;
    const startedAt = Date.now();
    try {
      setWatchlistFeedback("");
      setWatchlistSectionErr("");
      setWatchlistAddingSymbol(symbol);
      const watchlistId = await ensureDashboardWatchlistId();
      await apiFetch(`/api/watchlists/${watchlistId}/items/`, {
        token,
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol }),
      }).catch(() => {
        // duplicates are fine for V1
      });
      setWatchlistInput("");
      setWatchlistFeedback(`${symbol} saved to your watchlist.`);
      await fetchWatchlistsForSave();
    } catch {
      setWatchlistSectionErr("Something went wrong. Retry.");
    } finally {
      await waitForMinimum(startedAt);
      setWatchlistAddingSymbol("");
    }
  }

  async function removeTickerFromWatchlist(itemId) {
    if (!dashboardWatchlist?.id || !itemId) return;
    const startedAt = Date.now();
    try {
      setWatchlistFeedback("");
      setWatchlistSectionErr("");
      setWatchlistRemovingItemId(itemId);
      await apiFetch(`/api/watchlists/${dashboardWatchlist.id}/items/${itemId}/`, {
        token,
        method: "DELETE",
      });
      setWatchlistFeedback("Ticker removed.");
      await fetchWatchlistsForSave();
    } catch {
      setWatchlistSectionErr("Something went wrong. Retry.");
    } finally {
      await waitForMinimum(startedAt);
      setWatchlistRemovingItemId(null);
    }
  }
  useEffect(() => {
    localStorage.setItem("seenOnboarding", showOnboarding ? "0" : "1");
  }, [showOnboarding]);

  useEffect(() => {
    if (saveOpen) {
      fetchWatchlistsForSave();
    }
  }, [saveOpen, fetchWatchlistsForSave]);

  useEffect(() => {
    if (token) {
      fetchWatchlistsForSave();
    }
  }, [token, fetchWatchlistsForSave]);

  useEffect(() => {
    if (isBlockedPage(page)) {
      setPage("dashboard");
    }
  }, [page, isBlockedPage]);

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
    const startedAt = Date.now();
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
      await waitForMinimum(startedAt);
      setScreenLoading(false);
      e.target.value = "";
    }
  }
  // [NOTE-QUICK-ALERT-ACTION]
  async function createQuickAlert() {
    if (!quickAlertSym) return;
    const startedAt = Date.now();
    setQuickAlertErr("");
    setQuickAlertSaving(true);

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
    } finally {
      await waitForMinimum(startedAt);
      setQuickAlertSaving(false);
    }
  }

  function openQuickAlert(symbol, finalScore) {
    setQuickAlertSym(symbol);
    setQuickAlertFinal(
      finalScore != null && !Number.isNaN(Number(finalScore))
        ? Number(finalScore)
        : null
    );
    setQuickAlertMinFinal("");
    setQuickAlertTriggerOnce(true);
    setQuickAlertErr("");
  }

  function openChart(symbol, buttonLabel = "Chart") {
    const resolved = String(symbol || "").trim().toUpperCase();
    pushChartDebug(`Chart button clicked: ${buttonLabel}`, {
      button: buttonLabel,
      rawSymbol: symbol || null,
      handlerFired: true,
    });
    if (!resolved) {
      pushChartDebug("Chart action blocked: missing ticker", {
        button: buttonLabel,
        rawSymbol: symbol || null,
        blocked: true,
      });
      return;
    }
    pushChartDebug(`Chart fetch started for ${resolved} / range=D`, {
      symbol: resolved,
      range: "D",
      asyncStarted: true,
    });
    setChartSym(resolved);
  }

  function closeChart(reason = "manual") {
    if (chartSym) {
      pushChartDebug(`Chart drawer closed (${reason})`, {
        symbol: chartSym,
        reason,
      });
    }
    setChartSym(null);
  }

  useEffect(() => {
    if (!chartSym || !DEBUG_CHART) return;
    pushChartDebug(`Chart drawer rendered for ${chartSym}`, {
      symbol: chartSym,
      rendered: true,
    });
  }, [chartSym, pushChartDebug]);

  // [NOTE-ACTIONS] Explain
  async function openExplain(symbol) {
    const startedAt = Date.now();
    setExplainingSymbol(symbol);
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
    } finally {
      await waitForMinimum(startedAt);
      setExplainingSymbol(null);
    }
  }

  // [NOTE-ACTIONS] Save current tickers into a watchlist
  async function saveCurrentTickers() {
    const startedAt = Date.now();
    setSaveBusy(true);
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
    } finally {
      await waitForMinimum(startedAt);
      setSaveBusy(false);
    }
  }

  function number(n, d = 2) {
    return typeof n === "number" ? n.toFixed(d) : n;
  }

  function formatRelativeTime(ts) {
    if (!ts) return "Just now";
    const diffMs = Date.now() - new Date(ts).getTime();
    if (Number.isNaN(diffMs)) return "Just now";
    const minutes = Math.floor(diffMs / 60000);
    if (minutes < 1) return "Just now";
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    if (days < 7) return `${days}d ago`;
    return new Date(ts).toLocaleDateString();
  }

  // ==============================
  // [NOTE-UI] App Shell
  // ==============================
  if (!isAuthed) {
    if (route.kind === "articles-list") {
      return (
        <ArticlesListPage
          apiBase={BASE}
          token={token}
          isAuthed={isAuthed}
          user={user}
          onOpenArticle={(slug) => navigatePath(`/articles/${slug}`)}
          onNavigateDashboard={() => navigatePath("dashboard")}
          onLogout={logout}
          onSignUp={() => navigatePath("dashboard")}
          onLogIn={() => navigatePath("dashboard")}
        />
      );
    }
    if (route.kind === "article-detail") {
      return (
        <ArticleDetailPage
          apiBase={BASE}
          slug={route.slug}
          isAuthed={isAuthed}
          user={user}
          onBackToArticles={() => navigatePath("/articles")}
          onNavigateDashboard={() => navigatePath("dashboard")}
          onLogout={logout}
          onSignUp={() => navigatePath("dashboard")}
          onLogIn={() => navigatePath("dashboard")}
        />
      );
    }
    return <Landing />;
  }

  if (route.kind === "articles-list") {
    return (
      <ArticlesListPage
        apiBase={BASE}
        token={token}
        isAuthed={isAuthed}
        user={user}
        onOpenArticle={(slug) => navigatePath(`/articles/${slug}`)}
        onNavigateDashboard={() => navigatePath("dashboard")}
        onLogout={logout}
        onSignUp={() => navigatePath("dashboard")}
        onLogIn={() => navigatePath("dashboard")}
      />
    );
  }

  if (route.kind === "article-detail") {
    return (
      <ArticleDetailPage
        apiBase={BASE}
        slug={route.slug}
        isAuthed={isAuthed}
        user={user}
        onBackToArticles={() => navigatePath("/articles")}
        onNavigateDashboard={() => navigatePath("dashboard")}
        onLogout={logout}
        onSignUp={() => navigatePath("dashboard")}
        onLogIn={() => navigatePath("dashboard")}
      />
    );
  }

  return (
    <div className="app-shell">
      {/* NAVBAR */}
      <Navbar
        user={user}
        onLogout={logout}
        active={page}
        onNavigate={navigateToPage}
        v1Mode={V1_MODE}
      />

      <main className="app-main">
        {/* ==============================
          DASHBOARD PAGE
         ============================== */}
        {page === "dashboard" && (
          <>
            <MacroDashboardPage
              onSnapshotChange={(snapshot) => setMacroSnapshot(snapshot)}
            />

            {/* [NOTE-ONBOARDING-PANEL] */}
            {showOnboarding && (
              <div className="bg-indigo-950/40 border border-indigo-700/60 rounded-2xl p-4 flex flex-col sm:flex-row sm:items-start gap-4">
                <div className="flex-1">
                  <div className="text-sm font-semibold mb-1">
                    Welcome to Quantelle
                  </div>
                  <p className="text-xs text-slate-300 mb-2">
                    Here’s a quick path to get useful output in under a minute:
                  </p>
                  <ol className="list-decimal ml-4 space-y-1 text-xs text-slate-200">
                    <li>Enter a basket of tickers you care about.</li>
                    <li>Adjust tech vs fund weights and TA sub-weights.</li>
                    <li>
                      Click <span className="font-semibold">Rank</span> to rate
                      the basket.
                    </li>
                    <li>
                      Save tickers you like to
                      your <span className="font-semibold">Watchlist</span> below.
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
                    disabled={loading}
                    className="px-3 py-1.5 rounded-xl border border-slate-700 hover:bg-slate-900"
                  >
                    {loading ? "Loading..." : "Run first update"}
                  </button>
                </div>
              </div>
            )}

            {/* === your existing Dashboard CTA + controls + table === */}

            {/* CTA card */}
            <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-4 flex items-center justify-between">
              <div>
                <div className="text-lg font-semibold">Daily Market Decision Engine</div>
                <div className="text-sm text-slate-400">
                  Market Direction + top opportunities in one workflow
                </div>
                <div className="text-xs text-slate-500 mt-1">
                  Start with the highest Overall Rating, then open Chart or Why.
                </div>
              </div>
              <button
                onClick={rank}
                disabled={loading}
                className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-60 shadow"
              >
                {loading ? "Updating ratings..." : "Update ratings"}
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
                  TA sub-weights apply inside technical strength.
                </p>
              </div>
            </section>

            {/* Errors */}
            {!!errMsg && (
              <div className="bg-rose-950/50 text-rose-200 border border-rose-900 p-3 rounded-xl flex flex-wrap items-center justify-between gap-3">
                <div className="text-sm font-semibold">Something went wrong. Retry.</div>
                <button
                  onClick={rank}
                  disabled={loading}
                  className="px-3 py-1.5 rounded-lg border border-rose-700 text-xs hover:bg-rose-900/30 disabled:opacity-60"
                >
                  {loading ? "Loading..." : "Retry"}
                </button>
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
                  Top opportunities
                </div>
                <div className="flex items-center gap-2 text-xs">
                  <span className="text-slate-500">Spark period:</span>
                  {["1W", "1M", "3M"].map((p) => (
                    <button
                      key={p}
                      onClick={() => setSparkPeriod(p)}
                      disabled={loading}
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

              {loading && !rows.length ? (
                <div className="space-y-3" aria-live="polite">
                  {[0, 1, 2, 3, 4].map((idx) => (
                    <div
                      key={`ranker-skeleton-${idx}`}
                      className="h-10 rounded-lg bg-slate-800/60 animate-pulse"
                    />
                  ))}
                </div>
              ) : (
                <table className="w-full text-sm">
                  <thead className="text-slate-400">
                    <tr className="text-left">
                      <Th>Symbol</Th>
                      <Th>Live</Th>
                      <Th>Spark</Th>
                      <Th>Tech Strength</Th>
                      <Th>Fund Strength</Th>
                      <Th>Overall Rating</Th>
                      <Th>Trend</Th>
                      <Th>Momo</Th>
                      <Th>Vol</Th>
                      <Th>MeanRev</Th>
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
                          <Td className="text-emerald-200">
                            {liveQuotes[r.symbol]
                              ? `$${Number(liveQuotes[r.symbol]).toFixed(2)}`
                              : "—"}
                          </Td>
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

                        </tr>
                      );
                    })}
                    {!rows.length && !loading && (
                      <tr>
                        <td
                          className="py-6 text-center text-slate-500"
                          colSpan={9}
                        >
                          No data yet. Click "Update ratings".
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              )}
            </section>

            {DEBUG_CHART && (
              <section className="bg-amber-950/30 border border-amber-700/60 rounded-2xl p-3">
                <div className="flex items-center justify-between gap-2 mb-2">
                  <h3 className="text-sm font-semibold text-amber-100">Chart Debug (Temporary)</h3>
                  <button
                    type="button"
                    onClick={() => setChartDebugEvents([])}
                    className="text-xs px-2 py-1 rounded border border-amber-600 text-amber-200 hover:bg-amber-900/40"
                  >
                    Clear
                  </button>
                </div>
                <div className="max-h-44 overflow-y-auto space-y-1 text-xs">
                  {!chartDebugEvents.length && (
                    <div className="text-amber-200/80">No chart interactions yet.</div>
                  )}
                  {chartDebugEvents.map((evt) => (
                    <div key={evt.id} className="text-amber-100/95">
                      <span className="font-mono text-[11px] text-amber-300 mr-2">
                        {new Date(evt.at).toLocaleTimeString()}
                      </span>
                      <span>{evt.message}</span>
                    </div>
                  ))}
                </div>
              </section>
            )}

            <section className="bg-slate-900/50 border border-slate-800 rounded-2xl p-4">
              <div className="flex items-center justify-between gap-3 mb-3">
                <div>
                  <h3 className="text-base font-semibold">My Watchlist</h3>
                  <p className="text-xs text-slate-400">Save tickers here to track their latest ratings in one place.</p>
                </div>
              </div>

              <div className="flex flex-wrap gap-2 mb-3">
                <input
                  value={watchlistInput}
                  onChange={(e) => setWatchlistInput(e.target.value.toUpperCase())}
                  placeholder="Enter ticker (e.g., AAPL)"
                  className="bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm flex-1 min-w-[180px]"
                />
                <button
                  onClick={() => addTickerToWatchlist(watchlistInput)}
                  disabled={!watchlistInput.trim() || Boolean(watchlistAddingSymbol)}
                  className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-sm disabled:opacity-60"
                >
                  {watchlistAddingSymbol ? "Loading..." : "Add"}
                </button>
              </div>

              {watchlistFeedback && (
                <div className="mb-2 text-xs text-emerald-300">{watchlistFeedback}</div>
              )}
              {watchlistSectionErr && (
                <div className="mb-2 text-xs text-rose-300 flex items-center gap-2">
                  <span>{watchlistSectionErr}</span>
                  <button
                    onClick={fetchWatchlistsForSave}
                    className="px-2 py-1 rounded-md border border-rose-700 hover:bg-rose-900/20"
                  >
                    Retry
                  </button>
                </div>
              )}

              {watchlistSectionLoading ? (
                <div className="space-y-2" aria-live="polite">
                  {[0, 1, 2].map((idx) => (
                    <div key={`watchlist-skeleton-${idx}`} className="h-10 rounded-lg bg-slate-800/60 animate-pulse" />
                  ))}
                </div>
              ) : watchlistRows.length ? (
                <div className="space-y-2">
                  {watchlistRows.map((item) => (
                    <div key={item.id} className="flex flex-wrap items-center justify-between gap-3 border border-slate-800 rounded-xl px-3 py-2 text-sm">
                      <div>
                        <div className="font-semibold text-slate-100">{item.symbol}</div>
                        {item.name && <div className="text-xs text-slate-400">{item.name}</div>}
                      </div>
                      <div className="text-right">
                        <div className="text-xs text-slate-300">Rating: {item.rating}</div>
                        <div className="text-xs text-slate-500">{item.status}</div>
                      </div>
                      <button
                        onClick={() => removeTickerFromWatchlist(item.id)}
                        disabled={watchlistRemovingItemId === item.id}
                        className="px-3 py-1.5 rounded-lg text-xs border border-rose-900 text-rose-200 hover:bg-rose-950 disabled:opacity-60"
                      >
                        {watchlistRemovingItemId === item.id ? "Loading..." : "Remove"}
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-xs text-slate-400">No tickers saved yet. Add one above.</div>
              )}
            </section>

            <section className="bg-slate-900/35 border border-slate-800 rounded-2xl p-4">
              <div className="flex items-center justify-between gap-2 mb-3">
                <h3 className="text-sm font-semibold text-slate-200">Latest Insight</h3>
                <button
                  type="button"
                  onClick={() => navigatePath("/articles")}
                  className="text-xs text-slate-400 hover:text-slate-200"
                >
                  View all
                </button>
              </div>

              {latestInsightsLoading && (
                <p className="text-xs text-slate-500">Loading insights...</p>
              )}

              {!latestInsightsLoading && latestInsightsErr && (
                <p className="text-xs text-rose-300">{latestInsightsErr}</p>
              )}

              {!latestInsightsLoading && !latestInsightsErr && latestInsights.length === 0 && (
                <p className="text-xs text-slate-500">No insights published yet.</p>
              )}

              {!latestInsightsLoading && !latestInsightsErr && latestInsights.length > 0 && (
                <ul className="space-y-2">
                  {latestInsights.map((article) => (
                    <li key={article.slug}>
                      <button
                        type="button"
                        onClick={() => navigatePath(`/articles/${article.slug}`)}
                        className="text-sm text-left text-slate-300 hover:text-indigo-300 transition"
                      >
                        {article.title}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <footer className="pt-2 text-xs text-slate-500">
              © {new Date().getFullYear()} {APP_NAME}. All rights reserved.
            </footer>
          </>
        )}

        {/* ==============================
          OTHER PAGES
         ============================== */}
        {!V1_MODE && page === "alerts" && <Alerts />}

        {!V1_MODE && page === "watchlists" && (
          <Watchlists
            onUseTickers={(symbols) => {
              setTickers(symbols.join(","));
              navigateToPage("dashboard");
            }}
          />
        )}

        {!V1_MODE && page === "macro" && <MacroDashboardPage />}

        {!V1_MODE && page === "strategy-backtest" && <StrategyBacktestPage onNavigate={navigateToPage} />}

        {!V1_MODE && page === "orders" && <Orders />}

        {!V1_MODE && page === "positions" && <Positions />}

        {!V1_MODE && page === "performance" && <Performance />}

        {!V1_MODE && page === "leaderboards" && <Leaderboards />}

        {!V1_MODE && page === "bots" && (
          <BotsPage
            onSelectBot={(id) => {
              setSelectedBotId(id);
              setPage("bot-detail");
            }}
          />
        )}

        {!V1_MODE && page === "bot-detail" && selectedBotId && (
          <BotDetailPage
            botId={selectedBotId}
            onBack={() => setPage("bots")}
          />
        )}

        {!V1_MODE && page === "backtest-history" && <BacktestHistoryPage />}

        {!V1_MODE && page === "settings" && (
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

        {!V1_MODE && page === "strategies" && <StrategyBuilder />}
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
                  disabled={saveBusy}
                  className="px-3 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500"
                >
                  {saveBusy ? "Loading..." : "Save"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* QUICK ALERT MODAL — hidden in V1 */}

      {/* EXPLAIN DRAWER — hidden in V1 */}

      {/* CHART DRAWER — hidden in V1 */}
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
