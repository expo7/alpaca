import { useEffect, useMemo, useState } from "react";
import { useAuth } from "../AuthProvider.jsx";
import Toast from "../components/Toast.jsx";
import useQuotes from "../hooks/useQuotes.js";

const BASE = "http://127.0.0.1:8000";
const REFRESH_MS = 15000;

async function apiFetch(path, { token, ...opts } = {}) {
  const headers = { ...(opts.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${BASE}${path}`, { ...opts, headers });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg = data?.detail || JSON.stringify(data);
    throw new Error(msg);
  }
  return data;
}

export default function Positions() {
  const { token } = useAuth();
  const [positions, setPositions] = useState([]);
  const [portfolios, setPortfolios] = useState([]);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);
  const [actionMsg, setActionMsg] = useState("");
  const [actionErr, setActionErr] = useState("");
  const [toastState, setToastState] = useState(null);
  const [pageLoading, setPageLoading] = useState(false);
  const liveQuotes = useQuotes(positions.map((p) => p.symbol));
  const [pagination, setPagination] = useState({
    next: null,
    prev: null,
    count: 0,
    limit: 50,
    page: 1,
    offset: 0,
  });
  const [jumpPage, setJumpPage] = useState("");

  useEffect(() => {
    if (!token) return;
    const load = async (url = "/api/paper/positions/", explicitOffset = 0) => {
      try {
        const res = await fetch(`${BASE}${url}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data?.detail || "Failed to load positions");
        const { results, next, previous, count, limit } = Array.isArray(data)
          ? { results: data, next: null, previous: null, count: data.length, limit: data.length }
          : data;
        setPositions(Array.isArray(results) ? results : []);
        const computedLimit = limit || pagination.limit || 50;
        const offsetFromUrl = (() => {
          try {
            const u = new URL(`${BASE}${url}`);
            const raw = u.searchParams.get("offset");
            return raw ? Number(raw) : 0;
          } catch {
            return 0;
          }
        })();
        const offset = explicitOffset || offsetFromUrl;
        const pageNum = computedLimit ? Math.floor(offset / computedLimit) + 1 : 1;
        setPagination({
          next,
          prev: previous,
          count: count || 0,
          limit: computedLimit,
          page: pageNum,
          offset,
        });
        const ports = await apiFetch("/api/paper/portfolios/", { token });
        setPortfolios(Array.isArray(ports) ? ports : []);
        setErr("");
      } catch (e) {
        setErr(e.message || "Failed to load positions");
      } finally {
      }
    };
    setLoading(true);
    load().finally(() => setLoading(false));
    const id = setInterval(() => load(), REFRESH_MS);
    return () => clearInterval(id);
  }, [token]);

  useEffect(() => {
    if (!Object.keys(liveQuotes).length) return;
    setPositions((prev) =>
      prev.map((p) => ({
        ...p,
        live_price: liveQuotes[p.symbol] ?? p.live_price,
      }))
    );
  }, [liveQuotes]);

  const capsByPortfolio = useMemo(() => {
    const map = {};
    portfolios.forEach((p) => {
      map[p.id] = {
        equity: Number(p.equity || p.cash_balance || 0),
        maxSingle: Number(p.max_single_position_pct || 0),
        maxGross: Number(p.max_gross_exposure_pct || 0),
      };
    });
    return map;
  }, [portfolios]);

  const grossByPortfolio = useMemo(() => {
    const totals = {};
    positions.forEach((pos) => {
      const val = Math.abs(Number(pos.market_value || 0));
      totals[pos.portfolio] = (totals[pos.portfolio] || 0) + val;
    });
    return totals;
  }, [positions]);

  // warn toast when caps breached
  useEffect(() => {
    let breached = false;
    positions.forEach((pos) => {
      const caps = capsByPortfolio[pos.portfolio] || {};
      const equity = caps.equity || 0;
      const mv = Math.abs(Number(pos.market_value || 0));
      if (equity > 0) {
        if (caps.maxSingle && mv > equity * (caps.maxSingle / 100)) breached = true;
        const gross = grossByPortfolio[pos.portfolio] || 0;
        if (caps.maxGross && gross > equity * (caps.maxGross / 100)) breached = true;
      }
    });
    if (breached) {
      setToastState({
        msg: "Exposure cap breached on positions. Adjust sizing.",
        tone: "warn",
      });
    }
  }, [positions, capsByPortfolio, grossByPortfolio]);

  if (!token) return null;

  const callAction = async (id, action, body = {}) => {
    setActionErr("");
    setActionMsg("");
    try {
      await apiFetch(`/api/paper/positions/${id}/${action}/`, {
        token,
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      setActionMsg(`${action} executed.`);
    } catch (e) {
      setActionErr(e.message || "Action failed");
    }
  };

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold">Positions</h1>
          <p className="text-sm text-slate-400">
            Holdings with instrument metadata and exposure flags.
          </p>
        </div>
        <div className="text-[11px] text-slate-500">
          Market data mode: {import.meta.env.VITE_PAPER_DATA_MODE || "live"}
          <button
            onClick={() => window.location.reload()}
            className="ml-3 px-3 py-1 rounded-lg border border-slate-700 hover:bg-slate-800 text-xs"
          >
            Refresh now
          </button>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-3 text-xs">
        <div className="text-slate-500">
          Showing {positions.length} of {pagination.count} | page size {pagination.limit} | page{" "}
          {pagination.page} /{" "}
          {pagination.limit ? Math.max(1, Math.ceil((pagination.count || 0) / pagination.limit)) : 1} | rows{" "}
          {pagination.offset + 1}-{Math.min(pagination.offset + pagination.limit, pagination.count)}
        </div>
        <div className="flex gap-2">
        {pagination.prev && (
          <button
            onClick={() => {
              if (pagination.prev) {
                setPageLoading(true);
                setPositions([]);
                setToastState({ msg: "Loading previous page...", tone: "info" });
                fetch(`${BASE}${pagination.prev}`, {
                  headers: { Authorization: `Bearer ${token}` },
                })
                  .then((res) => res.json())
                  .then((data) => {
                    const { results, next, previous, count, limit } = data;
                    setPositions(Array.isArray(results) ? results : []);
                    const offset = (() => {
                      try {
                        const u = new URL(`${BASE}${pagination.prev}`);
                        const raw = u.searchParams.get("offset");
                        return raw ? Number(raw) : 0;
                      } catch {
                        return 0;
                      }
                    })();
                    const pageNum = limit ? Math.floor(offset / limit) + 1 : pagination.page;
                    setPagination({
                      next,
                      prev: previous,
                      count: count || pagination.count,
                      limit: limit || pagination.limit,
                      page: pageNum,
                    });
                  })
                  .catch(() => setErr("Failed to load previous page"))
                  .finally(() => setPageLoading(false));
              }
            }}
            disabled={pageLoading}
            className="px-3 py-1.5 rounded-lg border border-slate-700 hover:bg-slate-800 disabled:opacity-60"
          >
            Prev
          </button>
        )}
        {pagination.next && (
          <button
            onClick={() => {
              if (pagination.next) {
                setPageLoading(true);
                setPositions([]);
                setToastState({ msg: "Loading next page...", tone: "info" });
                fetch(`${BASE}${pagination.next}`, {
                  headers: { Authorization: `Bearer ${token}` },
                })
                  .then((res) => res.json())
                  .then((data) => {
                    const { results, next, previous, count, limit } = data;
                    setPositions(Array.isArray(results) ? results : []);
                    const offset = (() => {
                      try {
                        const u = new URL(`${BASE}${pagination.next}`);
                        const raw = u.searchParams.get("offset");
                        return raw ? Number(raw) : 0;
                      } catch {
                        return 0;
                      }
                    })();
                    const pageNum = limit ? Math.floor(offset / limit) + 1 : pagination.page;
                    setPagination({
                      next,
                      prev: previous,
                      count: count || pagination.count,
                      limit: limit || pagination.limit,
                      page: pageNum,
                    });
                  })
                  .catch(() => setErr("Failed to load next page"))
                  .finally(() => setPageLoading(false));
              }
            }}
            disabled={pageLoading}
            className="px-3 py-1.5 rounded-lg border border-slate-700 hover:bg-slate-800 disabled:opacity-60"
          >
            Next
          </button>
        )}
        </div>
        <div className="flex items-center gap-2">
          <span>Page size</span>
          <select
            value={pagination.limit}
            onChange={(e) => {
              const limit = Number(e.target.value);
              setPagination((p) => ({ ...p, limit }));
              const url = new URL(`${BASE}/api/paper/positions/`);
              url.searchParams.set("limit", limit);
              url.searchParams.set("offset", "0");
              setPageLoading(true);
              fetch(url.toString(), {
                headers: { Authorization: `Bearer ${token}` },
              })
                .then((res) => res.json())
                .then((data) => {
                  const { results, next, previous, count } = data;
                  setPositions(Array.isArray(results) ? results : []);
                  setPagination({ next, prev: previous, count: count || 0, limit, page: 1, offset: 0 });
                })
                .catch(() => setErr("Failed to change page size"))
                .finally(() => setPageLoading(false));
            }}
            className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1"
          >
            {[25, 50, 100].map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
          <input
            type="number"
            min="1"
            value={jumpPage}
            onChange={(e) => setJumpPage(e.target.value)}
            placeholder="Jump to page"
            className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1 w-28"
          />
          <button
            onClick={() => {
              const pageNum = Number(jumpPage);
              if (!pageNum || pageNum < 1) return;
              const offset = (pageNum - 1) * pagination.limit;
              setPageLoading(true);
              const url = new URL(`${BASE}/api/paper/positions/`);
              url.searchParams.set("limit", pagination.limit);
              url.searchParams.set("offset", offset);
              fetch(url.toString(), {
                headers: { Authorization: `Bearer ${token}` },
              })
                .then((res) => res.json())
                .then((data) => {
                  const { results, next, previous, count, limit } = data;
                  setPositions(Array.isArray(results) ? results : []);
                  const finalLimit = limit || pagination.limit;
                  setPagination({
                    next,
                    prev: previous,
                    count: count || 0,
                    limit: finalLimit,
                    page: pageNum,
                    offset,
                  });
                })
                .catch(() => setErr("Failed to load page"))
                .finally(() => setPageLoading(false));
            }}
            className="px-3 py-1.5 rounded-lg border border-slate-700 hover:bg-slate-800 text-xs disabled:opacity-60"
            disabled={pageLoading}
          >
            Go
          </button>
        </div>
      </div>
      {err && (
        <div className="text-xs text-rose-200 bg-rose-900/30 border border-rose-800 rounded-xl px-3 py-2">
          {err}
        </div>
      )}
      {actionErr && (
        <div className="text-xs text-rose-200 bg-rose-900/30 border border-rose-800 rounded-xl px-3 py-2">
          {actionErr}
        </div>
      )}
      {actionMsg && (
        <div className="text-xs text-amber-200 bg-amber-900/30 border border-amber-800 rounded-xl px-3 py-2">
          {actionMsg}
        </div>
      )}
      <Toast
        message={toastState?.msg}
        tone={toastState?.tone}
        onClose={() => setToastState(null)}
      />
      <div className="bg-slate-900/50 border border-slate-800 rounded-2xl overflow-auto">
        <table className="w-full text-sm">
          <thead className="text-slate-400 text-xs">
            <tr>
              <th className="px-3 py-2 text-left">Symbol</th>
              <th className="px-3 py-2 text-left">Instrument</th>
              <th className="px-3 py-2 text-left">Portfolio</th>
              <th className="px-3 py-2 text-left">Qty</th>
              <th className="px-3 py-2 text-left">Avg Price</th>
              <th className="px-3 py-2 text-left">Market Value</th>
              <th className="px-3 py-2 text-left">Unrealized</th>
          <th className="px-3 py-2 text-left">Caps</th>
          <th className="px-3 py-2 text-left">Actions</th>
        </tr>
      </thead>
      <tbody>
        {positions.map((pos) => {
              const caps = capsByPortfolio[pos.portfolio] || {};
              const equity = caps.equity || 0;
              const mv = Math.abs(Number(pos.market_value || 0));
              const singleExceeded =
                caps.maxSingle && equity > 0 && mv > equity * (caps.maxSingle / 100);
              const grossExceeded =
                caps.maxGross &&
                equity > 0 &&
                (grossByPortfolio[pos.portfolio] || 0) > equity * (caps.maxGross / 100);
              return (
                <tr key={pos.id} className="border-t border-slate-800 text-xs">
                  <td className="px-3 py-2 font-semibold">{pos.symbol}</td>
                  <td className="px-3 py-2 text-slate-400">
                    {pos.instrument?.exchange || "—"}{" "}
                    {pos.instrument?.asset_class ? `· ${pos.instrument?.asset_class}` : ""}
                  </td>
                  <td className="px-3 py-2">
                    {pos.portfolio_name || pos.portfolio}
                  </td>
                  <td className="px-3 py-2">{Number(pos.quantity).toLocaleString()}</td>
                  <td className="px-3 py-2">${Number(pos.avg_price).toFixed(2)}</td>
                  <td className="px-3 py-2">
                    ${Number(pos.market_value).toLocaleString(undefined, { maximumFractionDigits: 2 })}
                  </td>
                  <td className="px-3 py-2">
                    ${Number(pos.unrealized_pnl).toLocaleString(undefined, { maximumFractionDigits: 2 })}
                  </td>
                <td className="px-3 py-2">
                  <div className="flex gap-1 flex-wrap">
                    {singleExceeded && (
                      <span title="Single position cap breached" className="px-2 py-1 rounded-lg bg-rose-900/40 border border-rose-800 text-rose-100">
                        Single cap
                        </span>
                      )}
                      {grossExceeded && (
                        <span title="Gross exposure cap breached" className="px-2 py-1 rounded-lg bg-amber-900/40 border border-amber-800 text-amber-100">
                          Gross cap
                        </span>
                      )}
                      {!singleExceeded && !grossExceeded && (
                        <span className="text-slate-500">—</span>
                      )}
                    </div>
                </td>
                  <td className="px-3 py-2">
                    <div className="flex gap-2 text-[11px]">
                      <button
                        onClick={() => {
                          const target = prompt("Target % of equity (e.g. 10):", "10");
                          const limit = prompt("Optional limit price (blank for live):", "");
                          if (target) callAction(pos.id, "rebalance", { target_pct: target, limit_price: limit || undefined });
                        }}
                        className="px-2 py-1 rounded-lg border border-slate-700 hover:bg-slate-800"
                      >
                        Rebalance
                      </button>
                      <button
                        onClick={() => {
                          const limit = prompt("Optional limit price to close (blank for live):", "");
                          callAction(pos.id, "close", { limit_price: limit || undefined });
                        }}
                        className="px-2 py-1 rounded-lg border border-rose-800 text-rose-200 hover:bg-rose-950"
                      >
                        Close
                      </button>
                    </div>
                  </td>
              </tr>
            );
          })}
            {!positions.length && !loading && (
              <tr>
                <td className="px-3 py-4 text-center text-slate-500" colSpan={8}>
                  No positions yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
