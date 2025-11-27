import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "../AuthProvider.jsx";
import Toast from "../components/Toast.jsx";
import useQuotes from "../hooks/useQuotes.js";
import TradingViewChart from "../TradingViewChart.jsx";
import { simulateOrderFill } from "../api/paper.js";

const BASE = "http://127.0.0.1:8000";
const DATA_MODE = import.meta.env.VITE_PAPER_DATA_MODE || "live";
const QUOTE_REFRESH_MS = 20000;
const EDITABLE_TYPES = new Set([
  "limit",
  "hidden_limit",
  "iceberg",
  "stop",
  "stop_limit",
  "trailing_limit",
]);
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

const BTN_BASE =
  "transition-colors transition-transform duration-150 active:scale-[0.97] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900";
const BTN_GHOST = `${BTN_BASE} border border-slate-700 hover:bg-slate-800/70`;
const BTN_PRIMARY = `${BTN_BASE} bg-indigo-600 text-white hover:bg-indigo-500/90`;
const BTN_DANGER = `${BTN_BASE} border border-rose-700 text-rose-200 hover:bg-rose-900/40`;

export default function Orders() {
  const { token } = useAuth();
  const [orders, setOrders] = useState([]);
  const [portfolios, setPortfolios] = useState([]);
  const [watchlists, setWatchlists] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState({});
  const [savingOrderId, setSavingOrderId] = useState(null);
  const [cancelingOrderId, setCancelingOrderId] = useState(null);
  const [screenCache, setScreenCache] = useState({});
  const [screenLoadingKey, setScreenLoadingKey] = useState("");
  const [screenFetchError, setScreenFetchError] = useState("");
  const [auditState, setAuditState] = useState(null);
  const [auditLoading, setAuditLoading] = useState(false);
  const [overrideModal, setOverrideModal] = useState(null);
  const [auditPinned, setAuditPinned] = useState(null);
  const [showPinnedInModal, setShowPinnedInModal] = useState(false);
  const [detailModal, setDetailModal] = useState(null);
  const liveQuotes = useQuotes(orders.map((o) => o.symbol));
  const [toastState, setToastState] = useState(null);
  const [instrumentMeta, setInstrumentMeta] = useState({});
  const [capsByPortfolio, setCapsByPortfolio] = useState({});
  const [chartSymbol, setChartSymbol] = useState("");
  const [simulatingId, setSimulatingId] = useState(null);

  const formatCurrency = (value) => {
    const num = Number(value);
    if (!Number.isFinite(num)) return null;
    return num.toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  };

  const getLiveQuote = (symbol) =>
    liveQuotes[symbol] || liveQuotes[symbol?.toUpperCase()];

  const childCounts = useMemo(() => {
    const counts = {};
    orders.forEach((order) => {
      if (order.parent) {
        counts[order.parent] = (counts[order.parent] || 0) + 1;
      }
    });
    return counts;
  }, [orders]);

  const loadOrders = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const res = await fetch(`${BASE}/api/paper/orders/`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Failed to load orders");
      const data = await res.json();
      const arr = Array.isArray(data) ? data : [];
      setOrders(arr);
      // Auto-open detail modal when there's a pinned timeline and matching order
      if (!detailModal && auditPinned?.order?.id) {
        const match = arr.find((o) => o.id === auditPinned.order.id);
        if (match) {
          setAuditState({
            order: match,
            events: match.audit_events || match.notes?.events || [],
            trades: match.recent_trades || [],
          });
          setShowPinnedInModal(true);
          setDetailModal(match);
        }
      }
      setError("");
    } catch (err) {
      setError(err.message || "Failed to load orders");
    } finally {
      setLoading(false);
    }
  }, [token, auditPinned, detailModal]);

  const loadPortfolios = useCallback(async () => {
    if (!token) return;
    try {
      const res = await fetch(`${BASE}/api/paper/portfolios/`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Failed to load portfolios");
      const data = await res.json();
      setPortfolios(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error(err);
    }
  }, [token]);

  const loadWatchlists = useCallback(async () => {
    if (!token) return;
    try {
      const res = await fetch(`${BASE}/api/watchlists/`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Failed to load watchlists");
      const data = await res.json();
      setWatchlists(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error(err);
    }
  }, [token]);

  const fetchScreenSymbols = useCallback(
    async (screen) => {
      if (!token || !screen) return [];
      if (screenCache[screen]) return screenCache[screen];
      setScreenLoadingKey(screen);
      setScreenFetchError("");
      try {
        const res = await fetch(
          `${BASE}/api/default-tickers/aggressive-small-caps/?screen=${encodeURIComponent(
            screen
          )}`,
          {
            headers: { Authorization: `Bearer ${token}` },
          }
        );
        if (!res.ok) throw new Error("Failed to load universe");
        const data = await res.json();
        const symbols = data?.symbols || [];
        setScreenCache((prev) => ({ ...prev, [screen]: symbols }));
        return symbols;
      } catch (err) {
        setScreenFetchError(err.message || "Failed to load universe");
        throw err;
      } finally {
        setScreenLoadingKey("");
      }
    },
    [token, screenCache]
  );

  useEffect(() => {
    if (!token) return;
    loadOrders();
    loadPortfolios();
    loadWatchlists();
  }, [token, loadOrders, loadPortfolios, loadWatchlists]);

  useEffect(() => {
    if (!portfolios.length) return;
    setCapsByPortfolio(
      Object.fromEntries(
        portfolios.map((p) => [
          p.id,
          {
            equity: Number(p.equity || p.cash_balance || 0),
            maxPositions: p.max_positions,
            maxSingle: Number(p.max_single_position_pct || 0),
            maxGross: Number(p.max_gross_exposure_pct || 0),
          },
        ])
      )
    );
  }, [portfolios]);

  useEffect(() => {
    const symbols = Array.from(new Set(orders.map((o) => o.symbol)));
    const fetchMeta = async () => {
      const missing = symbols.filter((s) => !instrumentMeta[s]);
      for (const sym of missing) {
        try {
          const res = await fetch(
            `${BASE}/api/paper/instruments/?q=${encodeURIComponent(sym)}`
          );
          if (!res.ok) continue;
          const data = await res.json();
          if (Array.isArray(data) && data.length) {
            setInstrumentMeta((prev) => ({ ...prev, [sym]: data[0] }));
          }
        } catch {
          // ignore lookup failures
        }
      }
    };
    if (symbols.length && symbols.some((sym) => !instrumentMeta[sym])) fetchMeta();
  }, [orders, instrumentMeta]);

  useEffect(() => {
    if (!Object.keys(liveQuotes).length) return;
    setCapsByPortfolio((prev) => {
      const prevQuotes = prev.quotes || {};
      const sameSize = Object.keys(prevQuotes).length === Object.keys(liveQuotes).length;
      const sameValues =
        sameSize &&
        Object.entries(liveQuotes).every(([sym, price]) => prevQuotes[sym] === price);
      if (sameValues) return prev;
      return { ...prev, quotes: liveQuotes };
    });
  }, [liveQuotes]);

  useEffect(() => {
    if (auditState && auditPinned && auditPinned.order?.id === auditState.order?.id) {
      setShowPinnedInModal(true);
      setDetailModal(auditState.order);
    }
  }, [auditState, auditPinned]);

  async function handleSimulate(orderId) {
    // Debug logging to help trace button behavior
    // eslint-disable-next-line no-console
    console.log("[orders] check fill clicked", { orderId, hasToken: !!token });
    if (!token) return;
    setSimulatingId(orderId);
    try {
      const updated = await simulateOrderFill(orderId, token);
      // eslint-disable-next-line no-console
      console.log("[orders] check fill response", updated);
      setOrders((prev) => prev.map((o) => (o.id === orderId ? updated : o)));
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error("[orders] check fill error", err);
      setToastState({ msg: err.message || "Simulation failed", tone: "warn" });
    } finally {
      setSimulatingId(null);
    }
  }

  const loadAudit = async (order) => {
    if (!token) return;
    // Prefer inline audit data already on the order payload
    const inline = order
      ? {
          order,
          events: order.audit_events || order.notes?.events || [],
          trades: order.recent_trades || [],
          children: order.recent_children || [],
        }
      : null;
    if (inline && inline.events && inline.trades) {
      setAuditState(inline);
      setDetailModal(order);
      return;
    }
    setAuditLoading(true);
    try {
      const res = await fetch(`${BASE}/api/paper/orders/${order.id}/audit/`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Failed to fetch audit");
      const data = await res.json();
      setAuditState(data);
      setDetailModal(order);
    } catch (err) {
      setError(err.message || "Failed to load audit trail");
    } finally {
      setAuditLoading(false);
    }
  };

  const startEditing = (order) => {
    setEditing((prev) => ({
      ...prev,
      [order.id]: {
        limit_price: order.limit_price ?? "",
        stop_price: order.stop_price ?? "",
        slippage_mode: order.slippage_mode || "",
        slippage_bps: order.slippage_bps || "",
        slippage_fixed: order.slippage_fixed || "",
        fee_mode: order.fee_mode || "",
        fee_bps: order.fee_bps || "",
        fee_per_share: order.fee_per_share || "",
        max_fill_participation: order.max_fill_participation || "",
        min_fill_size: order.min_fill_size || "",
        backtest_fill_mode: order.backtest_fill_mode || "",
      },
    }));
  };

  const handleEditChange = (orderId, field, value) => {
    setEditing((prev) => ({
      ...prev,
      [orderId]: { ...prev[orderId], [field]: value },
    }));
  };

  const cancelInlineEdit = (orderId) => {
    setEditing((prev) => {
      const clone = { ...prev };
      delete clone[orderId];
      return clone;
    });
  };

  const submitEdit = async (order) => {
    if (!token || !editing[order.id]) return;
    const payload = {};
    const values = editing[order.id];
    if ("limit_price" in values && values.limit_price !== "") {
      payload.limit_price = Number(values.limit_price);
    }
    if ("stop_price" in values && values.stop_price !== "") {
      payload.stop_price = Number(values.stop_price);
    }
    // Inline cap check using edit prices + live quotes
    const caps = capsByPortfolio[order.portfolio] || {};
    const live = capsByPortfolio.quotes?.[order.symbol] || 0;
    const priceHint =
      Number(values.limit_price || values.stop_price || live || order.average_fill_price || 0);
    const notional = priceHint > 0 ? Number(order.quantity || 0) * priceHint : 0;
    if (
      notional &&
      caps.equity &&
      ((caps.maxSingle && notional > caps.equity * (caps.maxSingle / 100)) ||
        (caps.maxGross && notional + Math.abs(order.market_value || 0) > caps.equity * (caps.maxGross / 100)))
    ) {
      const proceed = window.confirm("Edited prices may breach exposure caps. Save anyway?");
      if (!proceed) return;
    }
    [
      "slippage_mode",
      "slippage_bps",
      "slippage_fixed",
      "fee_mode",
      "fee_bps",
      "fee_per_share",
      "max_fill_participation",
      "min_fill_size",
      "backtest_fill_mode",
    ].forEach((field) => {
      if (field in values && values[field] !== "") {
        payload[field] =
          typeof values[field] === "string" && !isNaN(values[field])
            ? Number(values[field])
            : values[field];
      }
    });
    if (!Object.keys(payload).length) {
      cancelInlineEdit(order.id);
      return;
    }
    try {
      setSavingOrderId(order.id);
      const res = await fetch(`${BASE}/api/paper/orders/${order.id}/`, {
        method: "PATCH",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error("Order update failed");
      cancelInlineEdit(order.id);
      loadOrders();
    } catch (err) {
      setError(err.message || "Failed to update order");
    } finally {
      setSavingOrderId(null);
    }
  };

  const cancelOrder = async (orderId) => {
    if (!token) return;
    if (!window.confirm("Cancel this order?")) return;
    try {
      setCancelingOrderId(orderId);
      const res = await fetch(`${BASE}/api/paper/orders/${orderId}/`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      if (!res.ok) throw new Error("Failed to cancel order");
      cancelInlineEdit(orderId);
      loadOrders();
    } catch (err) {
      setError(err.message || "Failed to cancel order");
    } finally {
      setCancelingOrderId(null);
    }
  };

  const renderPrices = (order) => {
    const editState = editing[order.id];
    const showLimit = order.limit_price !== null && order.limit_price !== undefined;
    const showStop = order.stop_price !== null && order.stop_price !== undefined;
    if (editState && EDITABLE_TYPES.has(order.order_type)) {
      return (
        <div className="flex flex-col gap-2">
          {showLimit && (
            <input
              type="number"
              value={editState.limit_price}
              onChange={(e) => handleEditChange(order.id, "limit_price", e.target.value)}
              className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1 text-xs"
            />
          )}
          {showStop && (
            <input
              type="number"
              value={editState.stop_price}
              onChange={(e) => handleEditChange(order.id, "stop_price", e.target.value)}
              className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1 text-xs"
            />
          )}
          <div className="grid grid-cols-2 gap-2 text-[11px]">
            <select
              value={editState.slippage_mode}
              onChange={(e) => handleEditChange(order.id, "slippage_mode", e.target.value)}
              className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1"
            >
              <option value="">slip default</option>
              <option value="bps">bps</option>
              <option value="fixed">fixed</option>
              <option value="none">none</option>
            </select>
            <select
              value={editState.fee_mode}
              onChange={(e) => handleEditChange(order.id, "fee_mode", e.target.value)}
              className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1"
            >
              <option value="">fee default</option>
              <option value="per_share">per share</option>
              <option value="bps">bps</option>
              <option value="none">none</option>
            </select>
            <input
              type="number"
              value={editState.slippage_bps}
              onChange={(e) => handleEditChange(order.id, "slippage_bps", e.target.value)}
              placeholder="slip bps"
              className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1"
            />
            <input
              type="number"
              value={editState.slippage_fixed}
              onChange={(e) => handleEditChange(order.id, "slippage_fixed", e.target.value)}
              placeholder="slip fixed"
              className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1"
            />
            <input
              type="number"
              value={editState.fee_bps}
              onChange={(e) => handleEditChange(order.id, "fee_bps", e.target.value)}
              placeholder="fee bps"
              className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1"
            />
            <input
              type="number"
              value={editState.fee_per_share}
              onChange={(e) => handleEditChange(order.id, "fee_per_share", e.target.value)}
              placeholder="fee/share"
              className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1"
            />
            <input
              type="number"
              value={editState.max_fill_participation}
              onChange={(e) => handleEditChange(order.id, "max_fill_participation", e.target.value)}
              placeholder="max part"
              className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1"
            />
            <input
              type="number"
              value={editState.min_fill_size}
              onChange={(e) => handleEditChange(order.id, "min_fill_size", e.target.value)}
              placeholder="min fill"
              className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1"
            />
            <select
              value={editState.backtest_fill_mode}
              onChange={(e) => handleEditChange(order.id, "backtest_fill_mode", e.target.value)}
              className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1 col-span-2"
            >
              <option value="">backtest fill</option>
              <option value="history">history</option>
              <option value="live">live</option>
            </select>
          </div>
          {!showLimit && !showStop && (
            <span className="text-xs text-slate-500">No editable prices</span>
          )}
        </div>
      );
    }
    return (
      <div className="text-xs space-y-1">
        {showLimit && (
          <div className="text-emerald-200">
            Limit: <span className="font-mono">{order.limit_price}</span>
          </div>
        )}
        {showStop && (
          <div className="text-rose-200">
            Stop: <span className="font-mono">{order.stop_price}</span>
          </div>
        )}
        {!showLimit && !showStop && <span className="text-slate-500">—</span>}
      </div>
    );
  };

  const chainBadge = (order) => {
    if (!order.chain_id) return "—";
    const hasChildren = childCounts[order.id] > 0;
    return (
      <div className="flex flex-col gap-1">
        <span className="px-2 py-1 text-xs rounded-xl bg-indigo-600/20 border border-indigo-500 text-indigo-100 w-fit">
          {order.chain_id}
        </span>
        {hasChildren && (
          <span className="text-[11px] text-slate-400">
            {childCounts[order.id]} linked exit{childCounts[order.id] > 1 ? "s" : ""}
          </span>
        )}
      </div>
    );
  };

  const roleBadge = (order) => {
    if (order.child_role) {
      return (
        <span className="px-2 py-1 text-xs rounded-xl bg-amber-600/20 border border-amber-500 text-amber-100">
          {order.child_role.toUpperCase()}
        </span>
      );
    }
    if (childCounts[order.id] > 0) {
      return (
        <span className="px-2 py-1 text-xs rounded-xl bg-emerald-700/20 border border-emerald-500 text-emerald-100">
          PARENT
        </span>
      );
    }
    return "—";
  };

  const renderActions = (order) => {
    const isEditable = EDITABLE_TYPES.has(order.order_type);
    const isEditing = !!editing[order.id];
    const canSimulate = ["new", "working", "part_filled"].includes(order.status);
    return (
      <div className="flex flex-wrap gap-2 text-xs">
        {isEditable && !isEditing && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              startEditing(order);
            }}
            className={`${BTN_GHOST} px-2 py-1 rounded-lg text-xs`}
          >
            Edit
          </button>
        )}
        {isEditable && isEditing && (
          <>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                submitEdit(order);
              }}
              disabled={savingOrderId === order.id}
              className={`${BTN_PRIMARY} px-2 py-1 rounded-lg text-xs disabled:opacity-60`}
            >
              {savingOrderId === order.id ? "Saving..." : "Save"}
            </button>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                cancelInlineEdit(order.id);
              }}
              className={`${BTN_GHOST} px-2 py-1 rounded-lg text-xs`}
            >
              Cancel
            </button>
          </>
        )}
        {canSimulate && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              handleSimulate(order.id);
            }}
            disabled={simulatingId === order.id}
            className={`${BTN_GHOST} px-2 py-1 rounded-lg text-xs disabled:opacity-60`}
          >
            {simulatingId === order.id ? "Checking…" : "Check fill"}
          </button>
        )}
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            cancelOrder(order.id);
          }}
          disabled={cancelingOrderId === order.id}
          className={`${BTN_DANGER} px-2 py-1 rounded-lg text-xs disabled:opacity-60`}
        >
          {cancelingOrderId === order.id ? "Canceling..." : "Cancel"}
        </button>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            setOverrideModal(order);
          }}
          className={`${BTN_GHOST} px-2 py-1 rounded-lg text-xs`}
        >
          Overrides
        </button>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            loadAudit(order);
          }}
          className={`${BTN_GHOST} px-2 py-1 rounded-lg text-xs`}
        >
          {auditLoading && auditState?.order?.id === order.id ? "Loading…" : "Audit"}
        </button>
      </div>
    );
  };

  if (!token) {
    return (
      <div className="p-4 text-sm text-amber-300">
        Login required to view orders.
      </div>
    );
  }

  return (
    <div className="p-4 lg:p-6 space-y-4">
      {chartSymbol && (
        <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-3 space-y-2">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Micro view · {chartSymbol} · 1m</span>
            <span className="text-[11px]">TradingView</span>
          </div>
          <div className="rounded-lg overflow-hidden border border-slate-800">
            <TradingViewChart
              symbol={chartSymbol}
              interval="1"
              exchangePrefix=""
              autosize={false}
              height={480}
            />
          </div>
        </div>
      )}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-lg font-semibold">Orders</h1>
          <p className="text-sm text-slate-400">
            Inline-manage bracket / OCO chains, exits, and algo orders.
          </p>
        </div>
        <button
          type="button"
          onClick={loadOrders}
          className={`${BTN_GHOST} px-3 py-1.5 rounded-xl text-xs`}
        >
          Refresh
        </button>
      </div>
      <div className="flex flex-wrap gap-2 text-[11px]">
        <span className="text-slate-400">
          Quotes refresh every {QUOTE_REFRESH_MS / 1000}s (mode: {DATA_MODE})
        </span>
      </div>
      {auditPinned && (
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-3 space-y-2 text-xs">
          <div className="flex items-center justify-between">
            <div className="font-semibold">
              Pinned timeline · Order #{auditPinned.order?.id} {auditPinned.order?.symbol}
            </div>
            <button
              type="button"
              onClick={() => setAuditPinned(null)}
              className={`${BTN_GHOST} text-[11px] px-2 py-1 rounded-lg`}
            >
              Unpin
            </button>
          </div>
          <Timeline events={(auditPinned.events || []).concat(auditPinned.order?.audit_events || [])} />
        </div>
      )}

      {error && (
        <div className="text-xs text-rose-200 bg-rose-900/30 border border-rose-800 rounded-xl px-3 py-2">
          {error}
        </div>
      )}

      <div className="bg-slate-900/50 border border-slate-800 rounded-xl overflow-auto">
        <div className="px-3 pt-3 text-xs text-slate-400">
          Caps = exposure cap hints, Prices = limit/stop values, Chain = bracket/linked order chain_id, Role = parent/child role.
        </div>
        <table className="w-full text-sm">
          <thead className="text-slate-400">
            <tr>
              <th className="px-3 py-2 text-left">Symbol</th>
              <th className="px-3 py-2 text-left">Instrument</th>
              <th className="px-3 py-2 text-left">Type</th>
              <th className="px-3 py-2 text-left">TIF</th>
              <th className="px-3 py-2 text-left">Qty/Notional</th>
              <th className="px-3 py-2 text-left">Live</th>
              <th className="px-3 py-2 text-left">Status</th>
              <th className="px-3 py-2 text-left">Caps</th>
              <th className="px-3 py-2 text-left">Prices</th>
              <th className="px-3 py-2 text-left">Chain</th>
              <th className="px-3 py-2 text-left">Role</th>
              <th className="px-3 py-2 text-left">Notes</th>
              <th className="px-3 py-2 text-left">Actions</th>
            </tr>
          </thead>
          <tbody>
            {!orders.length && (
              <tr>
                <td colSpan={13} className="px-3 py-4 text-center text-slate-500">
                  {loading ? "Loading..." : "No orders yet."}
                </td>
              </tr>
            )}
            {orders.map((order) => {
              const livePrice = getLiveQuote(order.symbol);
              const qty = Number(order.quantity || 0);
              const priceHint = Number(
                order.limit_price ??
                  order.stop_price ??
                  livePrice ??
                  order.average_fill_price ??
                  0
              );
              const notional =
                priceHint > 0 ? qty * priceHint : Number(order.notional || 0);
              const formattedNotional = formatCurrency(notional);
              const formattedLive = formatCurrency(livePrice);
              return (
                <tr
                  key={order.id}
                  className="border-t border-slate-800 align-top cursor-pointer hover:bg-slate-900/40"
                  onClick={() => {
                    setDetailModal(order);
                    loadAudit(order);
                  }}
                >
                  <td className="px-3 py-2 font-semibold">{order.symbol}</td>
                  <td className="px-3 py-2 text-xs text-slate-400">
                    {(instrumentMeta[order.symbol]?.exchange || instrumentMeta[order.symbol]?.asset_class) ? (
                      <>
                        {instrumentMeta[order.symbol]?.exchange || ""}
                        {instrumentMeta[order.symbol]?.exchange && instrumentMeta[order.symbol]?.asset_class ? " · " : ""}
                        {instrumentMeta[order.symbol]?.asset_class || ""}
                      </>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="px-3 py-2 text-xs">
                    {order.order_type.replace(/_/g, " ")}
                  </td>
                  <td className="px-3 py-2 text-xs">
                    {order.tif?.toUpperCase?.() === "DAY"
                      ? "End of Day"
                      : order.tif?.toUpperCase?.() === "GTC"
                      ? "Good 'Til Canceled"
                      : order.tif || "—"}
                  </td>
                  <td className="px-3 py-2 text-xs">
                    <div className="space-y-1">
                      <div className="flex items-baseline gap-2">
                        <span className="font-semibold text-sm">
                          {Number(order.quantity ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                        </span>
                        <span className="text-[11px] text-slate-400">Qty</span>
                      </div>
                      <div className="text-[11px] text-slate-300">
                        Est. notional:{" "}
                        {formattedNotional ? `$${formattedNotional}` : "—"}
                      </div>
                    </div>
                  </td>
                  <td className="px-3 py-2 text-xs text-emerald-200">
                    {formattedLive ? `Live: $${formattedLive}` : "Live: —"}
                  </td>
                  <td className="px-3 py-2">
                    <span className="px-2 py-1 rounded-xl bg-slate-800 text-xs inline-flex gap-1 items-center">
                    {order.status}
                    {(order.audit_events || []).some((e) => e.event === "liquidity_queue") && (
                      <span
                        className="px-2 py-0.5 rounded-lg bg-amber-900/50 text-amber-200 text-[10px]"
                        title={
                          order.audit_events.find((e) => e.bar_ts)?.bar_ts
                            ? `Waiting for next bar at ${order.audit_events.find((e) => e.bar_ts)?.bar_ts}`
                            : "Waiting for liquidity"
                        }
                      >
                        queued
                      </span>
                    )}
                    {order.status === "working" && !order.audit_events?.length && (
                      <span
                        className="px-2 py-0.5 rounded-lg bg-slate-800 text-slate-300 text-[10px]"
                        title={
                          order.audit_events?.find((e) => e.bar_ts)?.bar_ts
                            ? `Waiting for liquidity; next bar ${order.audit_events.find((e) => e.bar_ts)?.bar_ts}`
                            : "Waiting for fills"
                        }
                      >
                        pending
                      </span>
                    )}
                    {order.status === "working" && (
                      <span
                        className="px-2 py-0.5 rounded-lg bg-slate-700 text-slate-200 text-[10px]"
                        title={
                          order.audit_events?.find((e) => e.bar_ts)?.bar_ts
                            ? `Waiting for liquidity; next bar ${order.audit_events.find((e) => e.bar_ts)?.bar_ts}`
                            : "Waiting for liquidity"
                        }
                      >
                        ⏳
                      </span>
                    )}
                    {order.status === "rejected" &&
                      (order.notes?.detail?.toLowerCase().includes("cap") ? (
                        <span className="text-rose-300">cap</span>
                      ) : null)}
                  </span>
                </td>
                <td className="px-3 py-2">
                  <CapBadges
                    order={order}
                    capsByPortfolio={capsByPortfolio}
                    onWarn={(msg) =>
                      setToastState({ msg, tone: "warn" })
                    }
                  />
                </td>
                <td className="px-3 py-2">{renderPrices(order)}</td>
                <td className="px-3 py-2">{chainBadge(order)}</td>
                <td className="px-3 py-2">{roleBadge(order)}</td>
                <td className="px-3 py-2 text-xs text-slate-400 space-y-1">
                  {(order.notes?.events || []).slice(-2).map((evt, idx) => {
                    const isFill = (evt.event || "").toLowerCase() === "fill";
                    return (
                      <div key={`${order.id}-evt-${idx}`} className="flex items-center gap-2">
                        {evt.event && (
                          <span
                            className={`px-2 py-0.5 rounded-lg text-[11px] font-semibold ${
                              isFill
                                ? "bg-emerald-900/40 border border-emerald-700 text-emerald-200"
                                : "bg-slate-800 border border-slate-700 text-slate-200"
                            }`}
                          >
                            {evt.event}
                          </span>
                        )}
                        <span className="text-slate-400">{evt.child || evt.count || ""}</span>
                      </div>
                    );
                  })}
                  {(order.audit_events || []).some((e) => e.event === "liquidity_queue") && (
                    <div className="text-amber-300">
                      Queued for next bar{" "}
                      {order.audit_events.find((e) => e.bar_ts)?.bar_ts
                        ? `(${order.audit_events.find((e) => e.bar_ts)?.bar_ts})`
                        : ""}
                    </div>
                  )}
                  {detailModal?.id === order.id && auditPinned && (
                    <div className="text-[11px] text-slate-300">
                      Timeline pinned in detail view
                    </div>
                  )}
                </td>
                <td className="px-3 py-2">{renderActions(order)}</td>
              </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <BracketForm
        token={token}
        portfolios={portfolios}
        watchlists={watchlists}
        screenHelpers={{
          fetchScreenSymbols,
          screenChoices: SCREEN_CHOICES,
          loadingKey: screenLoadingKey,
          error: screenFetchError,
        }}
        onSuccess={loadOrders}
        onSymbolChange={setChartSymbol}
      />
      {overrideModal && (
        <OverrideModal
          order={overrideModal}
          onClose={() => setOverrideModal(null)}
          onChange={(payload) => handleEditChange(overrideModal.id, payload.field, payload.value)}
          onSave={() => {
            submitEdit(overrideModal);
            setOverrideModal(null);
          }}
        />
      )}
      {auditState && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-4 space-y-3 text-sm max-w-4xl w-full max-h-[80vh] overflow-auto">
            <div className="flex items-center justify-between">
              <div className="font-semibold">
                Audit · Order #{auditState.order?.id} ({auditState.order?.symbol})
              </div>
              <button
                type="button"
                onClick={() => setAuditState(null)}
                className={`${BTN_GHOST} text-xs px-2 py-1 rounded-lg`}
              >
                Close
              </button>
            </div>
            <div className="flex gap-2 text-[11px]">
              <button
                type="button"
                onClick={() => setAuditPinned(auditState)}
                className={`${BTN_GHOST} px-2 py-1 rounded-lg`}
              >
                Pin timeline
              </button>
              {auditPinned && auditPinned.order?.id === auditState.order?.id && (
                <span className="text-emerald-300">Pinned</span>
              )}
              {auditPinned && (
                <button
                  type="button"
                  onClick={() => setShowPinnedInModal((v) => !v)}
                  className={`${BTN_GHOST} px-2 py-1 rounded-lg`}
                >
                  {showPinnedInModal ? "Hide pinned here" : "Show pinned here"}
                </button>
              )}
            </div>
            {(auditState.events || []).some((e) => e.event === "liquidity_queue") && (
              <div className="text-[11px] px-3 py-2 rounded-lg bg-amber-900/30 border border-amber-800 text-amber-100">
                Queued for liquidity — waiting for next bar (see events timeline).
              </div>
            )}
            <div className="grid md:grid-cols-2 gap-4">
              <div>
                <div className="text-[11px] uppercase text-slate-400 mb-1">Events</div>
                <div className="bg-slate-950 border border-slate-800 rounded-lg max-h-48 overflow-auto divide-y divide-slate-800">
                  <Timeline events={(auditState.events || []).concat(auditState.order?.audit_events || [])} />
                </div>
                {showPinnedInModal && auditPinned && (
                  <div className="mt-2">
                    <div className="text-[11px] uppercase text-slate-400 mb-1">Pinned Timeline</div>
                    <div className="bg-slate-950 border border-slate-800 rounded-lg max-h-40 overflow-auto divide-y divide-slate-800">
                      <Timeline events={(auditPinned.events || []).concat(auditPinned.order?.audit_events || [])} />
                    </div>
                  </div>
                )}
              </div>
              <div>
                <div className="text-[11px] uppercase text-slate-400 mb-1">Trades</div>
                <div className="bg-slate-950 border border-slate-800 rounded-lg max-h-48 overflow-auto divide-y divide-slate-800">
                  {(auditState.trades || []).length ? (
                    auditState.trades.map((t) => (
                      <div key={t.id} className="px-3 py-2 text-xs flex justify-between">
                        <div className="space-y-1">
                          <div className="font-semibold">
                            {t.side.toUpperCase()} {t.quantity} @ {t.price}
                          </div>
                          <div className="text-slate-400 font-mono">{t.created_at}</div>
                        </div>
                        <div className="text-right text-slate-300">
                          Fees: {t.fees} <br />
                          Slippage: {t.slippage}
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="px-3 py-3 text-slate-500">No trades</div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
      <Toast
        message={toastState?.msg}
        tone={toastState?.tone}
        onClose={() => setToastState(null)}
      />
    </div>
  );
}

function BracketForm({ token, portfolios, watchlists, screenHelpers, onSuccess, onSymbolChange }) {
  const [form, setForm] = useState({
    portfolio: "",
    symbol: "",
    side: "buy",
    order_type: "market",
    quantity: "",
    tif: "day",
    limit_price: "",
    take_profit: "",
    stop_loss: "",
    slippage_mode: "",
    slippage_bps: "",
    slippage_fixed: "",
    fee_mode: "",
    fee_bps: "",
    fee_per_share: "",
    max_fill_participation: "",
    min_fill_size: "",
    backtest_fill_mode: "",
  });
  const [backtestProfile, setBacktestProfile] = useState({
    fill_mode: "",
    participation: "",
  });
  const backtestPresets = [
    { label: "Default", fill_mode: "", participation: "" },
    { label: "VWAP 10%", fill_mode: "history", participation: "0.10" },
    { label: "VWAP 25%", fill_mode: "history", participation: "0.25" },
    { label: "Live (no cap)", fill_mode: "live", participation: "" },
  ];
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [selectedWatchlist, setSelectedWatchlist] = useState("");
  const [selectedWatchlistSymbol, setSelectedWatchlistSymbol] = useState("");
  const [selectedScreen, setSelectedScreen] = useState("");
  const [selectedScreenSymbol, setSelectedScreenSymbol] = useState("");
  const [screenSymbols, setScreenSymbols] = useState([]);
  const [screenErr, setScreenErr] = useState("");
  const [screenLoading, setScreenLoading] = useState(false);
  const [instrumentResults, setInstrumentResults] = useState([]);
  const [instrumentQuery, setInstrumentQuery] = useState("");
  const [instrumentLoading, setInstrumentLoading] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const formQuotes = useQuotes(form.symbol ? [form.symbol] : []);
  const [yfPrice, setYfPrice] = useState(null);
  const [yfPriceSymbol, setYfPriceSymbol] = useState("");
  const [yfPriceLoading, setYfPriceLoading] = useState(false);
  const [yfPriceError, setYfPriceError] = useState("");
  const [showCosts, setShowCosts] = useState(false);
  const [showBacktest, setShowBacktest] = useState(false);
  const formatCurrencyLocal = (value) => {
    const num = Number(value);
    if (!Number.isFinite(num) || num <= 0) return null;
    return num.toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  };

  const updateField = (field, value) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const resetForm = () => {
    setForm((prev) => ({
      ...prev,
      symbol: "",
      quantity: "",
      limit_price: "",
      take_profit: "",
      stop_loss: "",
    }));
  };

  const selectedPortfolio = useMemo(
    () => portfolios.find((p) => String(p.id) === String(form.portfolio)),
    [portfolios, form.portfolio]
  );
  const capViolation = submitError?.toLowerCase().includes("cap");
  const liveFormPrice =
    formQuotes[form.symbol] ||
    formQuotes[form.symbol?.toUpperCase()] ||
    (yfPriceSymbol &&
    (form.symbol?.toUpperCase() === yfPriceSymbol ||
      instrumentQuery?.toUpperCase() === yfPriceSymbol)
      ? yfPrice
      : null);
  const estPrice = Number(form.limit_price || liveFormPrice || 0);
  const estNotional = estPrice > 0 ? Number(form.quantity || 0) * estPrice : 0;
  const formattedFormQuote = formatCurrencyLocal(liveFormPrice);
  const formattedFormNotional = formatCurrencyLocal(estNotional);
  const capPreview =
    selectedPortfolio && estNotional > 0
      ? {
          single:
            selectedPortfolio.max_single_position_pct &&
            estNotional >
              Number(selectedPortfolio.equity || selectedPortfolio.cash_balance || 0) *
                (Number(selectedPortfolio.max_single_position_pct) / 100),
          gross:
            selectedPortfolio.max_gross_exposure_pct &&
            estNotional >
              Number(selectedPortfolio.equity || selectedPortfolio.cash_balance || 0) *
                (Number(selectedPortfolio.max_gross_exposure_pct) / 100),
        }
      : null;

  const currentWatchlist = useMemo(
    () =>
      (watchlists || []).find(
        (wl) => String(wl.id) === String(selectedWatchlist)
      ),
    [watchlists, selectedWatchlist]
  );
  const watchlistSymbols = currentWatchlist?.items || [];

  const onWatchlistSelect = (e) => {
    const value = e.target.value;
    setSelectedWatchlist(value);
    setSelectedWatchlistSymbol("");
  };

  const onWatchlistSymbolSelect = (e) => {
    const value = e.target.value;
    setSelectedWatchlistSymbol(value);
    if (value) {
      updateField("symbol", value);
    }
  };

  const handleScreenChange = async (e) => {
    const screen = e.target.value;
    setSelectedScreen(screen);
    setSelectedScreenSymbol("");
    setScreenSymbols([]);
    setScreenErr("");
    if (!screen || !screenHelpers?.fetchScreenSymbols) return;
    setScreenLoading(true);
    try {
      const symbols = await screenHelpers.fetchScreenSymbols(screen);
      setScreenSymbols(symbols);
    } catch (err) {
      setScreenErr(err.message || "Failed to load universe");
    } finally {
      setScreenLoading(false);
    }
  };

  const searchInstruments = async () => {
    if (!instrumentQuery.trim()) return;
    setInstrumentLoading(true);
    try {
      const res = await fetch(
        `${BASE}/api/paper/instruments/?q=${encodeURIComponent(instrumentQuery)}`
      );
      if (!res.ok) throw new Error("Lookup failed");
      const data = await res.json();
      setInstrumentResults(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error(err);
    } finally {
      setInstrumentLoading(false);
    }
  };

  const parseError = async (res) => {
    try {
      const data = await res.json();
      if (data?.detail) return data.detail;
      if (typeof data === "string") return data;
      return JSON.stringify(data);
    } catch {
      return `${res.status} ${res.statusText}`;
    }
  };

  const handleScreenSymbolSelect = (e) => {
    const value = e.target.value;
    setSelectedScreenSymbol(value);
    if (value) {
      updateField("symbol", value);
    }
  };

  const fetchOneMinutePrice = async () => {
    const candidateSymbol = form.symbol?.trim().toUpperCase();
    if (!candidateSymbol) {
      setYfPriceError("Enter a symbol first.");
      return;
    }
    try {
      setYfPriceLoading(true);
      setYfPriceError("");
      const res = await fetch(
        `${BASE}/api/paper/symbols/${encodeURIComponent(
          candidateSymbol
        )}/interval/?interval=1m&period=max`
      );
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(detail || "Quote lookup failed");
      }
      const data = await res.json();
      setYfPrice(data?.last_close ?? null);
      setYfPriceSymbol((data?.symbol || candidateSymbol).toUpperCase());
    } catch (err) {
      setYfPrice(null);
      setYfPriceSymbol("");
      setYfPriceError(err.message || "Quote lookup failed");
    } finally {
      setYfPriceLoading(false);
    }
  };

  useEffect(() => {
    // reset manual 1m price when symbol changes
    setYfPrice(null);
    setYfPriceSymbol("");
    setYfPriceError("");
  }, [form.symbol]);

  const applySymbolChange = () => {
    if (!onSymbolChange) return;
    const sym = form.symbol?.trim().toUpperCase() || "";
    onSymbolChange(sym);
  };

  const submit = async (e) => {
    e.preventDefault();
    if (!token) return;
    if (!form.portfolio || !form.symbol || !form.quantity) {
      setError("Portfolio, symbol, and quantity are required.");
      return;
    }
    setSubmitting(true);
    setError("");
    setSubmitError("");
    try {
      const payload = {
        portfolio: Number(form.portfolio),
        symbol: form.symbol.trim().toUpperCase(),
        side: form.side,
        order_type: form.order_type,
        tif: form.tif,
        quantity: Number(form.quantity),
        extended_hours: true,
      };
      if (backtestProfile.fill_mode) {
        payload.backtest_fill_mode = backtestProfile.fill_mode;
      }
      if (backtestProfile.participation) {
        payload.max_fill_participation = Number(backtestProfile.participation);
      }
      if (form.order_type === "limit" && form.limit_price) {
        payload.limit_price = Number(form.limit_price);
      }
      const overrides = {};
      if (form.slippage_mode) overrides.slippage_mode = form.slippage_mode;
      ["slippage_bps", "slippage_fixed", "fee_bps", "fee_per_share", "max_fill_participation", "min_fill_size"].forEach(
        (field) => {
          if (form[field]) {
            overrides[field] = Number(form[field]);
          }
        }
      );
      if (form.fee_mode) overrides.fee_mode = form.fee_mode;
      if (form.backtest_fill_mode) overrides.backtest_fill_mode = form.backtest_fill_mode;
      Object.assign(payload, overrides);
      if (capPreview && (capPreview.single || capPreview.gross)) {
        const proceed = window.confirm("Live quote sizing suggests a cap breach. Submit anyway?");
        if (!proceed) {
          setSubmitting(false);
          return;
        }
      }
      const res = await fetch(`${BASE}/api/paper/orders/`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const detail = await parseError(res);
        throw new Error(detail || "Parent order failed");
      }
      const parent = await res.json();
      const chainId = parent.chain_id || `chain-${parent.id}`;
      const childPayloads = [];
      if (form.take_profit) {
        childPayloads.push({
          portfolio: Number(form.portfolio),
          parent: parent.id,
          symbol: parent.symbol,
          side: parent.side === "buy" ? "sell" : "buy",
          order_type: "limit",
          limit_price: Number(form.take_profit),
          quantity: Number(form.quantity),
          tif: form.tif,
          chain_id: chainId,
          child_role: "tp",
          ...overrides,
        });
      }
      if (form.stop_loss) {
        childPayloads.push({
          portfolio: Number(form.portfolio),
          parent: parent.id,
          symbol: parent.symbol,
          side: parent.side === "buy" ? "sell" : "buy",
          order_type: "stop",
          stop_price: Number(form.stop_loss),
          quantity: Number(form.quantity),
          tif: form.tif,
          chain_id: chainId,
          child_role: "sl",
          ...overrides,
        });
      }
      for (const child of childPayloads) {
        const childRes = await fetch(`${BASE}/api/paper/orders/`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify(child),
        });
        if (!childRes.ok) {
          const detail = await parseError(childRes);
          throw new Error(detail || "Failed to create linked exit");
        }
      }
      resetForm();
      onSuccess?.();
    } catch (err) {
      setError(err.message || "Failed to submit bracket");
      setSubmitError(err.message || "Failed to submit bracket");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form
      onSubmit={submit}
      className="bg-slate-900/50 border border-slate-800 rounded-xl p-4 space-y-3 text-sm"
    >
      <div className="font-semibold">Quick bracket / OCO</div>
      {error && <div className="text-xs text-rose-300">{error}</div>}
      {submitError && (
        <div className="text-xs text-rose-200 bg-rose-900/30 border border-rose-800 rounded-lg px-3 py-2">
          {submitError}
        </div>
      )}
      <div className="grid md:grid-cols-4 gap-3 text-xs">
        <select
          value={form.portfolio}
          onChange={(e) => updateField("portfolio", e.target.value)}
          className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-0.5 text-xs h-8 w-full md:w-48"
        >
          <option value="">Select portfolio</option>
          {portfolios.map((portfolio) => (
            <option key={portfolio.id} value={portfolio.id}>
              {portfolio.name}
            </option>
          ))}
        </select>
        <div className="space-y-2">
          <div className="flex gap-2 items-center">
            <input
              value={form.symbol}
              onChange={(e) => updateField("symbol", e.target.value)}
              placeholder="Symbol"
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5"
            />
            <button
              type="button"
              onClick={applySymbolChange}
              className={`${BTN_GHOST} px-2 py-1 rounded-lg text-[11px] whitespace-nowrap`}
            >
              Set symbol
            </button>
          </div>
          <div className="hidden">
            <div className="flex gap-2">
              <input
                value={instrumentQuery}
                onChange={(e) => setInstrumentQuery(e.target.value)}
                placeholder="Lookup symbol…"
                className="flex-1 bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5"
              />
              <button
                type="button"
                onClick={searchInstruments}
                className={`${BTN_GHOST} px-3 py-1.5 rounded-lg text-xs`}
              >
                {instrumentLoading ? "..." : "Search"}
              </button>
            </div>
            <div className="text-[11px] text-slate-400 flex items-center gap-2">
              <span>Live price:</span>
              <span className="font-semibold text-emerald-200">
                {yfPriceLoading
                  ? "Loading..."
                  : yfPrice
                  ? `$${formatCurrencyLocal(yfPrice)}`
                  : "—"}
              </span>
              {yfPriceError && <span className="text-rose-300">{yfPriceError}</span>}
            </div>
            {instrumentResults.length > 0 && (
              <div className="bg-slate-950 border border-slate-800 rounded-lg max-h-32 overflow-auto">
                {instrumentResults.map((inst) => (
                  <button
                    key={inst.id || inst.symbol}
                    type="button"
                    className={`${BTN_BASE} w-full text-left px-3 py-1.5 rounded-lg hover:bg-slate-800/70 text-[12px] flex justify-between`}
                    onClick={() => updateField("symbol", inst.symbol)}
                  >
                    <span className="font-semibold">{inst.symbol}</span>
                    <span className="text-slate-400 text-right">
                      {inst.exchange ? `${inst.exchange} · ` : ""}
                      {inst.asset_class}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
        <input
          value={form.quantity}
          onChange={(e) => updateField("quantity", e.target.value)}
          placeholder="Quantity"
          className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-0.5 text-xs h-8 w-full md:w-32"
        />
        <select
          value={form.side}
          onChange={(e) => updateField("side", e.target.value)}
          className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-0.5 text-xs h-8 w-full md:w-28"
        >
          <option value="buy">Buy</option>
          <option value="sell">Sell</option>
        </select>
      </div>
      <div className="bg-slate-950 border border-slate-800 rounded-lg p-3 text-xs flex flex-wrap items-baseline justify-between gap-3">
        <div className="flex items-center gap-3 flex-wrap">
          <div className="text-[11px] uppercase text-slate-400">Price &amp; Cost</div>
          <div className="text-[11px] text-slate-500">
            Fetch 1m price on demand to size your order.
          </div>
          <button
            type="button"
            onClick={fetchOneMinutePrice}
            disabled={!form.symbol || yfPriceLoading}
            className={`${BTN_GHOST} px-2 py-1 rounded-lg text-[11px] disabled:opacity-60`}
          >
            {yfPriceLoading ? "Fetching..." : "Get 1m price"}
          </button>
        </div>
        <div className="flex flex-wrap gap-4 items-end">
          <div>
            <div className="text-[11px] text-slate-400">Live</div>
            <div className="font-semibold text-emerald-200">
              {yfPriceLoading
                ? "Loading..."
                : formattedFormQuote
                ? `$${formattedFormQuote}`
                : "—"}
            </div>
              {yfPriceError && (
              <div className="text-[11px] text-rose-300">{yfPriceError}</div>
            )}
          </div>
          <div>
            <div className="text-[11px] text-slate-400">Est. cost</div>
            <div className="font-semibold text-slate-100">
              {formattedFormNotional ? `$${formattedFormNotional}` : "—"}
            </div>
            <div className="text-[11px] text-slate-500">
              {form.limit_price
                ? "using limit price"
                : formattedFormQuote
                ? "using live quote"
                : "awaiting quote"}
            </div>
          </div>
        </div>
      </div>
      <div className="grid md:grid-cols-5 gap-3 text-xs">
        <select
          value={form.order_type}
          onChange={(e) => updateField("order_type", e.target.value)}
          className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5"
        >
          <option value="market">Market</option>
          <option value="limit">Limit</option>
        </select>
        <select
          value={form.tif}
          onChange={(e) => updateField("tif", e.target.value)}
          className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5"
        >
          <option value="day">End of Day (DAY)</option>
          <option value="gtc">Good 'Til Canceled (GTC)</option>
        </select>
        {form.order_type === "limit" && (
          <input
            value={form.limit_price}
            onChange={(e) => updateField("limit_price", e.target.value)}
            placeholder="Limit price"
            className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5"
          />
        )}
        <input
          value={form.take_profit}
          onChange={(e) => updateField("take_profit", e.target.value)}
          placeholder="Take profit limit"
          className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5"
        />
        <input
          value={form.stop_loss}
          onChange={(e) => updateField("stop_loss", e.target.value)}
          placeholder="Stop loss price"
          className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5"
        />
      </div>
      <div className="flex items-center justify-between text-[11px] text-slate-400">
        <span>Advanced costs (slippage & fees)</span>
        <button
          type="button"
          onClick={() => setShowCosts((v) => !v)}
          className={`${BTN_GHOST} px-2 py-1 rounded-lg text-[11px]`}
        >
          {showCosts ? "Hide costs" : "Show costs"}
        </button>
      </div>
      {showCosts && (
        <div className="grid md:grid-cols-2 gap-3 text-xs">
          <div className="space-y-2">
            <div className="text-[11px] text-slate-400">Slippage</div>
            <select
              value={form.slippage_mode}
              onChange={(e) => updateField("slippage_mode", e.target.value)}
              className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5"
            >
              <option value="">Default (bps)</option>
              <option value="bps">bps</option>
              <option value="fixed">fixed</option>
              <option value="none">none</option>
            </select>
            <div className="flex gap-2">
              <input
                value={form.slippage_bps}
                onChange={(e) => updateField("slippage_bps", e.target.value)}
                placeholder="Slippage bps"
                className="flex-1 bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5"
              />
              <input
                value={form.slippage_fixed}
                onChange={(e) => updateField("slippage_fixed", e.target.value)}
                placeholder="Fixed ($)"
                className="flex-1 bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5"
              />
            </div>
          </div>
          <div className="space-y-2">
            <div className="text-[11px] text-slate-400">Fees</div>
            <select
              value={form.fee_mode}
              onChange={(e) => updateField("fee_mode", e.target.value)}
              className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5"
            >
              <option value="">Default (per-share)</option>
              <option value="per_share">per share</option>
              <option value="bps">bps</option>
              <option value="none">none</option>
            </select>
            <div className="flex gap-2">
              <input
                value={form.fee_bps}
                onChange={(e) => updateField("fee_bps", e.target.value)}
                placeholder="Fee bps"
                className="flex-1 bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5"
              />
              <input
                value={form.fee_per_share}
                onChange={(e) => updateField("fee_per_share", e.target.value)}
                placeholder="Fee per share"
                className="flex-1 bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5"
              />
            </div>
          </div>
        </div>
      )}
      <div className="flex items-center justify-between text-[11px] text-slate-400">
        <span>Backtest fills & defaults</span>
        <button
          type="button"
          onClick={() => setShowBacktest((v) => !v)}
          className={`${BTN_GHOST} px-2 py-1 rounded-lg text-[11px]`}
        >
          {showBacktest ? "Hide backtest" : "Show backtest"}
        </button>
      </div>
      {showBacktest && (
        <div className="grid md:grid-cols-1 gap-3 text-xs">
          <div className="space-y-2">
            <div className="text-[11px] text-slate-400">Backtest fills</div>
            <select
              value={form.backtest_fill_mode}
              onChange={(e) => updateField("backtest_fill_mode", e.target.value)}
              className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5"
            >
              <option value="">Default</option>
              <option value="history">History VWAP</option>
              <option value="live">Live</option>
            </select>
            <div className="flex gap-2">
              <input
                value={form.max_fill_participation}
                onChange={(e) => updateField("max_fill_participation", e.target.value)}
                placeholder="Max participation (0-1)"
                className="flex-1 bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5"
              />
              <input
                value={form.min_fill_size}
                onChange={(e) => updateField("min_fill_size", e.target.value)}
                placeholder="Min fill size"
                className="flex-1 bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5"
              />
            </div>
            <div className="text-[11px] text-slate-500">
              Controls bar VWAP slices + volume participation in backtests.
            </div>
            <div className="space-y-2">
              <div className="text-[11px] text-slate-400">Backtest profile (defaults)</div>
              <div className="flex gap-2">
                <select
                  value={backtestProfile.fill_mode}
                  onChange={(e) =>
                    setBacktestProfile((p) => ({ ...p, fill_mode: e.target.value }))
                  }
                  className="flex-1 bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5"
                >
                  <option value="">Use setting</option>
                  <option value="history">History VWAP</option>
                  <option value="live">Live</option>
                </select>
                <input
                  value={backtestProfile.participation}
                  onChange={(e) =>
                    setBacktestProfile((p) => ({ ...p, participation: e.target.value }))
                  }
                  placeholder="Default max participation"
                  className="flex-1 bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5"
                />
              </div>
              <div className="text-[11px] text-slate-500">
                Applied to new orders unless overridden above.
              </div>
              <div className="flex gap-2 flex-wrap">
                {backtestPresets.map((preset) => (
                  <button
                    key={preset.label}
                    type="button"
                    onClick={() => setBacktestProfile({ fill_mode: preset.fill_mode, participation: preset.participation })}
                    className={`${BTN_GHOST} px-2 py-1 rounded-lg text-[11px]`}
                  >
                    {preset.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
      <div className="hidden">
        {selectedPortfolio && (
          <div className="text-[11px] text-slate-400">
            Caps:{" "}
            {selectedPortfolio.max_positions
              ? `${selectedPortfolio.max_positions} positions`
              : "—"}{" "}
            | Single pos %:{" "}
            {selectedPortfolio.max_single_position_pct || "—"} | Gross %:{" "}
            {selectedPortfolio.max_gross_exposure_pct || "—"}
          </div>
        )}
        {estNotional > 0 && (
          <div className="text-[11px] text-slate-300">
            Est. notional ~ {formattedFormNotional ? `$${formattedFormNotional}` : estNotional.toLocaleString()} (price using{" "}
            {form.limit_price ? "limit" : liveFormPrice ? "live quote" : "qty only"})
            {capPreview && (capPreview.single || capPreview.gross) && (
              <span className="text-rose-300 ml-2">Possible cap breach</span>
            )}
          </div>
        )}
        {capViolation && (
          <div className="inline-flex items-center gap-2 text-[11px] px-3 py-2 rounded-lg bg-rose-900/30 border border-rose-800 text-rose-100">
            Exposure cap violation — adjust size or allocate another portfolio.
          </div>
        )}
        <div className="text-[11px] text-slate-500">
          Market data mode: {DATA_MODE}
        </div>
        <div className="grid md:grid-cols-2 gap-4 text-xs">
          <div className="space-y-2">
            <label className="text-slate-300 text-[13px]">From watchlist</label>
            <select
              value={selectedWatchlist}
              onChange={onWatchlistSelect}
              className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5"
            >
              <option value="">Select watchlist…</option>
              {(watchlists || []).map((wl) => (
                <option key={wl.id} value={wl.id}>
                  {wl.name} ({wl.items?.length || 0})
                </option>
              ))}
            </select>
            <select
              value={selectedWatchlistSymbol}
              onChange={onWatchlistSymbolSelect}
              disabled={!watchlistSymbols.length}
              className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5 disabled:opacity-60"
            >
              <option value="">
                {watchlistSymbols.length
                  ? "Pick a symbol to fill"
                  : "No symbols in list"}
              </option>
              {watchlistSymbols.map((item) => (
                <option key={item.id} value={item.symbol}>
                  {item.symbol}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-2">
            <label className="text-slate-300 text-[13px]">
              From scorer universe
            </label>
            <select
              value={selectedScreen}
              onChange={handleScreenChange}
              className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5"
            >
              <option value="">Select universe…</option>
              {(screenHelpers?.screenChoices || SCREEN_CHOICES).map((screen) => (
                <option key={screen} value={screen}>
                  {screen.replace(/_/g, " ")}
                </option>
              ))}
            </select>
            <select
              value={selectedScreenSymbol}
              onChange={handleScreenSymbolSelect}
              disabled={!screenSymbols.length && !screenLoading}
              className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5 disabled:opacity-60"
            >
              <option value="">
                {screenLoading
                  ? "Loading symbols…"
                  : screenSymbols.length
                  ? "Pick symbol"
                  : "No symbols loaded"}
              </option>
              {screenSymbols.map((symbol) => (
                <option key={symbol} value={symbol}>
                  {symbol}
                </option>
              ))}
            </select>
            {(screenErr || screenHelpers?.error) && (
              <p className="text-rose-300 text-[11px]">
                {screenErr || screenHelpers?.error}
              </p>
            )}
          </div>
        </div>
      </div>
      <button
        type="submit"
        disabled={submitting}
        className={`${BTN_PRIMARY} px-3 py-1.5 rounded-xl text-xs disabled:opacity-60`}
      >
        {submitting ? "Submitting..." : "Create order"}
      </button>
    </form>
  );
}

function CapBadges({ order, capsByPortfolio, onWarn }) {
  const caps = capsByPortfolio[order.portfolio] || {};
  const quotes = capsByPortfolio.quotes || {};
  if (!caps.equity || (!caps.maxSingle && !caps.maxGross)) {
    return <span className="text-slate-500 text-xs">—</span>;
  }
  const qty = Number(order.quantity || 0);
  const live = quotes[order.symbol] || quotes[order.symbol?.toUpperCase()];
  const priceHint = Number(
    order.limit_price ||
      order.stop_price ||
      live ||
      order.average_fill_price ||
      0
  );
  const notional = priceHint > 0 ? qty * priceHint : Number(order.notional || 0);
  const single = caps.maxSingle
    ? notional > caps.equity * (caps.maxSingle / 100)
    : false;
  const gross = caps.maxGross
    ? notional > caps.equity * (caps.maxGross / 100)
    : false;
  if ((single || gross) && onWarn) {
    onWarn("Exposure cap warning: check size before sending.");
  }
  return (
    <div className="flex gap-1 flex-wrap text-[11px]">
      {single && (
        <span
          title="Single position cap may be exceeded"
          className="px-2 py-1 rounded-lg bg-rose-900/40 border border-rose-800 text-rose-100"
        >
          Single cap
        </span>
      )}
      {gross && (
        <span
          title="Gross exposure cap may be exceeded"
          className="px-2 py-1 rounded-lg bg-amber-900/40 border border-amber-800 text-amber-100"
        >
          Gross cap
        </span>
      )}
      {!single && !gross && <span className="text-slate-500">—</span>}
    </div>
  );
}

function OverrideModal({ order, onClose, onChange, onSave }) {
  const fields = [
    { key: "slippage_mode", label: "Slippage mode" },
    { key: "slippage_bps", label: "Slippage bps" },
    { key: "slippage_fixed", label: "Slippage fixed" },
    { key: "fee_mode", label: "Fee mode" },
    { key: "fee_bps", label: "Fee bps" },
    { key: "fee_per_share", label: "Fee per share" },
    { key: "max_fill_participation", label: "Max participation" },
    { key: "min_fill_size", label: "Min fill size" },
    { key: "backtest_fill_mode", label: "Backtest mode" },
  ];
  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 w-full max-w-lg space-y-3">
        <div className="flex items-center justify-between">
          <div className="font-semibold text-sm">
            Overrides · Order #{order.id}
          </div>
          <button
            onClick={onClose}
            className={`${BTN_GHOST} text-xs px-2 py-1 rounded-lg`}
          >
            Close
          </button>
        </div>
        <div className="grid grid-cols-2 gap-2 text-xs">
          {fields.map((f) => (
            <label key={f.key} className="space-y-1">
              <span className="text-slate-400 text-[11px]">{f.label}</span>
              <input
                defaultValue={order[f.key] || ""}
                onChange={(e) =>
                  onChange({ field: f.key, value: e.target.value })
                }
                className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2 py-1"
              />
            </label>
          ))}
        </div>
        <div className="flex justify-end gap-2 text-xs">
          <button
            onClick={onClose}
            className={`${BTN_GHOST} px-3 py-1 rounded-lg text-xs`}
          >
            Cancel
          </button>
          <button
            onClick={onSave}
            className={`${BTN_PRIMARY} px-3 py-1 rounded-lg text-xs`}
          >
            Save overrides
          </button>
        </div>
      </div>
    </div>
  );
}

function Timeline({ events }) {
  const ordered = (events || [])
    .filter((e) => e.event)
    .sort((a, b) => (a.timestamp || "").localeCompare(b.timestamp || ""));
  if (!ordered.length) {
    return <div className="px-3 py-3 text-slate-500">No events</div>;
  }
  return ordered.map((evt, idx) => (
    <div key={`evt-${idx}`} className="px-3 py-2 text-xs">
      <div className="font-mono text-[11px] text-slate-400">
        {evt.timestamp || "—"}
      </div>
      <div className="text-emerald-100 flex items-center gap-2">
        {evt.event}
        {(evt.bar_ts || evt.liquidity_cap) && (
          <span className="px-2 py-0.5 rounded-lg bg-amber-900/40 border border-amber-800 text-amber-100 text-[10px]">
            queued
          </span>
        )}
      </div>
      <div className="text-slate-300">
        {Object.entries(evt)
          .filter(([k]) => k !== "event" && k !== "timestamp")
          .map(([k, v]) => (
            <span key={k} className="mr-2">
              {k}: {v}
            </span>
          ))}
      </div>
    </div>
  ));
}
