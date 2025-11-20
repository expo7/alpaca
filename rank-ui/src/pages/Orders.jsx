import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "../AuthProvider.jsx";

const BASE = "http://127.0.0.1:8000";
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
      setOrders(Array.isArray(data) ? data : []);
      setError("");
    } catch (err) {
      setError(err.message || "Failed to load orders");
    } finally {
      setLoading(false);
    }
  }, [token]);

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

  const startEditing = (order) => {
    setEditing((prev) => ({
      ...prev,
      [order.id]: {
        limit_price: order.limit_price ?? "",
        stop_price: order.stop_price ?? "",
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
    return (
      <div className="flex flex-wrap gap-2 text-xs">
        {isEditable && !isEditing && (
          <button
            type="button"
            onClick={() => startEditing(order)}
            className="px-2 py-1 rounded-lg border border-slate-700 hover:border-indigo-400"
          >
            Edit
          </button>
        )}
        {isEditable && isEditing && (
          <>
            <button
              type="button"
              onClick={() => submitEdit(order)}
              disabled={savingOrderId === order.id}
              className="px-2 py-1 rounded-lg bg-indigo-600 text-white disabled:opacity-60"
            >
              {savingOrderId === order.id ? "Saving..." : "Save"}
            </button>
            <button
              type="button"
              onClick={() => cancelInlineEdit(order.id)}
              className="px-2 py-1 rounded-lg border border-slate-700"
            >
              Cancel
            </button>
          </>
        )}
        <button
          type="button"
          onClick={() => cancelOrder(order.id)}
          disabled={cancelingOrderId === order.id}
          className="px-2 py-1 rounded-lg border border-rose-700 text-rose-200 disabled:opacity-60"
        >
          {cancelingOrderId === order.id ? "Canceling..." : "Cancel"}
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
          className="px-3 py-1.5 rounded-xl border border-slate-700 text-xs"
        >
          Refresh
        </button>
      </div>

      {error && (
        <div className="text-xs text-rose-200 bg-rose-900/30 border border-rose-800 rounded-xl px-3 py-2">
          {error}
        </div>
      )}

      <div className="bg-slate-900/50 border border-slate-800 rounded-xl overflow-auto">
        <table className="w-full text-sm">
          <thead className="text-slate-400">
            <tr>
              <th className="px-3 py-2 text-left">Symbol</th>
              <th className="px-3 py-2 text-left">Type</th>
              <th className="px-3 py-2 text-left">Qty/Notional</th>
              <th className="px-3 py-2 text-left">Status</th>
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
                <td colSpan={9} className="px-3 py-4 text-center text-slate-500">
                  {loading ? "Loading..." : "No orders yet."}
                </td>
              </tr>
            )}
            {orders.map((order) => (
              <tr key={order.id} className="border-t border-slate-800 align-top">
                <td className="px-3 py-2 font-semibold">{order.symbol}</td>
                <td className="px-3 py-2 text-xs">
                  {order.order_type.replace(/_/g, " ")}
                </td>
                <td className="px-3 py-2">
                  {order.quantity ?? order.notional ?? "—"}
                </td>
                <td className="px-3 py-2">
                  <span className="px-2 py-1 rounded-xl bg-slate-800 text-xs">
                    {order.status}
                  </span>
                </td>
                <td className="px-3 py-2">{renderPrices(order)}</td>
                <td className="px-3 py-2">{chainBadge(order)}</td>
                <td className="px-3 py-2">{roleBadge(order)}</td>
                <td className="px-3 py-2 text-xs text-slate-400 space-y-1">
                  {(order.notes?.events || []).slice(-2).map((evt, idx) => (
                    <div key={`${order.id}-evt-${idx}`}>
                      [{evt.event}] {evt.child || evt.count || ""}
                    </div>
                  ))}
                </td>
                <td className="px-3 py-2">{renderActions(order)}</td>
              </tr>
            ))}
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
      />
    </div>
  );
}

function BracketForm({ token, portfolios, watchlists, screenHelpers, onSuccess }) {
  const [form, setForm] = useState({
    portfolio: "",
    symbol: "",
    side: "buy",
    order_type: "market",
    quantity: "",
    limit_price: "",
    take_profit: "",
    stop_loss: "",
  });
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

  const handleScreenSymbolSelect = (e) => {
    const value = e.target.value;
    setSelectedScreenSymbol(value);
    if (value) {
      updateField("symbol", value);
    }
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
    try {
      const payload = {
        portfolio: Number(form.portfolio),
        symbol: form.symbol.trim().toUpperCase(),
        side: form.side,
        order_type: form.order_type,
        tif: "day",
        quantity: Number(form.quantity),
        extended_hours: true,
      };
      if (form.order_type === "limit" && form.limit_price) {
        payload.limit_price = Number(form.limit_price);
      }
      const res = await fetch(`${BASE}/api/paper/orders/`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error("Parent order failed");
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
          tif: "day",
          chain_id: chainId,
          child_role: "tp",
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
          tif: "day",
          chain_id: chainId,
          child_role: "sl",
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
          throw new Error("Failed to create linked exit");
        }
      }
      resetForm();
      onSuccess?.();
    } catch (err) {
      setError(err.message || "Failed to submit bracket");
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
      <div className="grid md:grid-cols-4 gap-3 text-xs">
        <select
          value={form.portfolio}
          onChange={(e) => updateField("portfolio", e.target.value)}
          className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5"
        >
          <option value="">Select portfolio</option>
          {portfolios.map((portfolio) => (
            <option key={portfolio.id} value={portfolio.id}>
              {portfolio.name}
            </option>
          ))}
        </select>
        <div className="space-y-2">
          <input
            value={form.symbol}
            onChange={(e) => updateField("symbol", e.target.value)}
            placeholder="Symbol"
            className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5"
          />
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
              className="px-3 py-1.5 rounded-lg border border-slate-700"
            >
              {instrumentLoading ? "..." : "Search"}
            </button>
          </div>
          {instrumentResults.length > 0 && (
            <div className="bg-slate-950 border border-slate-800 rounded-lg max-h-32 overflow-auto">
              {instrumentResults.map((inst) => (
                <button
                  key={inst.id || inst.symbol}
                  type="button"
                  className="w-full text-left px-3 py-1.5 hover:bg-slate-800 text-[12px] flex justify-between"
                  onClick={() => updateField("symbol", inst.symbol)}
                >
                  <span className="font-semibold">{inst.symbol}</span>
                  <span className="text-slate-400">{inst.asset_class}</span>
                </button>
              ))}
            </div>
          )}
        </div>
        <input
          value={form.quantity}
          onChange={(e) => updateField("quantity", e.target.value)}
          placeholder="Quantity"
          className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5"
        />
        <select
          value={form.side}
          onChange={(e) => updateField("side", e.target.value)}
          className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5"
        >
          <option value="buy">Buy</option>
          <option value="sell">Sell</option>
        </select>
      </div>
      <div className="grid md:grid-cols-4 gap-3 text-xs">
        <select
          value={form.order_type}
          onChange={(e) => updateField("order_type", e.target.value)}
          className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5"
        >
          <option value="market">Market</option>
          <option value="limit">Limit</option>
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
      <button
        type="submit"
        disabled={submitting}
        className="px-3 py-1.5 rounded-xl bg-indigo-600 text-white text-xs disabled:opacity-60"
      >
        {submitting ? "Submitting..." : "Create order"}
      </button>
    </form>
  );
}
