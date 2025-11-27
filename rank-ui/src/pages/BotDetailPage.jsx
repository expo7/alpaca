import { useEffect, useMemo, useState } from "react";
import { useAuth } from "../AuthProvider.jsx";
import {
  fetchBot,
  fetchBotForwardRuns,
  fetchBotLatestForwardRun,
  previewBot,
  startBot,
  pauseBot,
  stopBot,
} from "../api/bots.js";
import { fetchBotOrders, simulateOrderFill } from "../api/paper.js";
import Sparkline from "../components/Sparkline.jsx";

export default function BotDetailPage({ botId, onBack }) {
  const { token } = useAuth();
  const [bot, setBot] = useState(null);
  const [forwardRuns, setForwardRuns] = useState([]);
  const [latestForward, setLatestForward] = useState(null);
  const [preview, setPreview] = useState(null);
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [previewLoading, setPreviewLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [simulatingId, setSimulatingId] = useState(null);

  useEffect(() => {
    if (!botId || !token) return;
    setLoading(true);
    setError("");
    Promise.all([
      fetchBot(botId, token),
      fetchBotLatestForwardRun(botId, token),
      fetchBotForwardRuns(botId, token),
      fetchBotOrders(botId, token).catch(() => []),
    ])
      .then(([botData, latest, runs, ords]) => {
        setBot(botData);
        setLatestForward(latest);
        setForwardRuns(Array.isArray(runs) ? runs : []);
        const normalizedOrders = Array.isArray(ords) ? ords : ords?.results || [];
        setOrders(normalizedOrders);
      })
      .catch((err) => {
        setError(err.message || "Failed to load bot details");
      })
      .finally(() => setLoading(false));
  }, [botId, token]);

  const sparkData = useMemo(
    () => forwardRuns.map((r) => Number(r.equity || 0)),
    [forwardRuns]
  );

  async function handlePreview() {
    if (!token || !botId) return;
    setPreviewLoading(true);
    setError("");
    try {
      const data = await previewBot(botId, token);
      setPreview(data);
    } catch (err) {
      setError(err.message || "Failed to fetch preview");
    } finally {
      setPreviewLoading(false);
    }
  }

  async function handleAction(action) {
    if (!token || !botId) return;
    setActionLoading(true);
    try {
      let updated;
      if (action === "start") updated = await startBot(botId, token);
      if (action === "pause") updated = await pauseBot(botId, token);
      if (action === "stop") updated = await stopBot(botId, token);
      if (updated) setBot(updated);
    } catch (err) {
      setError(err.message || `Failed to ${action} bot`);
    } finally {
      setActionLoading(false);
    }
  }

  async function handleCheckFill(orderId) {
    // Debug logging to observe button wiring
    // eslint-disable-next-line no-console
    console.log("[bot-detail] check fill clicked", { orderId, hasToken: !!token });
    if (!token) return;
    setSimulatingId(orderId);
    try {
      const updated = await simulateOrderFill(orderId, token);
      // eslint-disable-next-line no-console
      console.log("[bot-detail] check fill response", updated);
      setOrders((prev) => prev.map((o) => (o.id === orderId ? updated : o)));
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error("[bot-detail] check fill error", err);
      setError(err.message || "Check fill failed");
    } finally {
      setSimulatingId(null);
    }
  }

  if (!botId) {
    return (
      <div className="p-4 text-sm text-rose-300">
        No bot selected.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onBack}
            className="px-3 py-1 rounded-lg border border-slate-700 text-xs hover:bg-slate-900"
          >
            ← Back
          </button>
          <div>
            <div className="text-lg font-semibold">{bot?.name || `Bot ${botId}`}</div>
            <div className="text-sm text-slate-400">
              Mode: <span className="font-semibold">{bot?.mode}</span> · State:{" "}
              <span className="font-semibold">{bot?.state}</span>
            </div>
            <div className="text-xs text-slate-500">
              Symbols: {(bot?.symbols || []).join(", ")}
            </div>
          </div>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            className="btn-primary text-xs disabled:opacity-60"
            onClick={() => handleAction("start")}
            disabled={actionLoading}
          >
            Start
          </button>
          <button
            type="button"
            className="btn-secondary text-xs disabled:opacity-60"
            onClick={() => handleAction("pause")}
            disabled={actionLoading}
          >
            Pause
          </button>
          <button
            type="button"
            className="btn-secondary text-xs disabled:opacity-60"
            onClick={() => handleAction("stop")}
            disabled={actionLoading}
          >
            Stop
          </button>
        </div>
      </div>

      {error && (
        <div className="text-xs text-rose-300 bg-rose-900/40 border border-rose-800 rounded-xl p-3">
          {error}
        </div>
      )}

      {loading ? (
        <div className="text-sm text-slate-300">Loading bot...</div>
      ) : (
        <>
          <div className="grid lg:grid-cols-2 gap-4">
            <div className="space-y-3">
              <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="text-sm font-semibold">Forward snapshot</div>
                  <div className="text-[11px] text-slate-400">
                    Last run:{" "}
                    {bot?.last_forward_run_at
                      ? new Date(bot.last_forward_run_at).toLocaleDateString()
                      : "—"}
                  </div>
                </div>
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-xs text-slate-400">Equity</div>
                    <div className="text-lg font-semibold text-emerald-200">
                      {latestForward?.equity
                        ? `$${Number(latestForward.equity).toLocaleString()}`
                        : bot?.last_forward_equity
                        ? `$${Number(bot.last_forward_equity).toLocaleString()}`
                        : "—"}
                    </div>
                  </div>
                  <Sparkline data={sparkData} width={160} height={48} />
                </div>
              </div>

              <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-sm font-semibold">Preview signals</div>
                    <div className="text-[11px] text-slate-400">
                      Hypothetical actions using latest 1m data.
                    </div>
                  </div>
                  <button
                    type="button"
                    className="btn-secondary text-xs disabled:opacity-60"
                    onClick={handlePreview}
                    disabled={previewLoading}
                  >
                    {previewLoading ? "Refreshing…" : "Refresh preview"}
                  </button>
                </div>
                {preview ? (
                  <div className="space-y-2">
                    <div className="text-xs text-slate-300">
                      Would trade?{" "}
                      <span className={preview.would_trade ? "text-emerald-300" : "text-slate-400"}>
                        {preview.would_trade ? "Yes" : "No"}
                      </span>
                    </div>
                    <div className="bg-slate-950 border border-slate-800 rounded-xl p-2 text-xs space-y-1">
                      <div className="font-semibold text-slate-200">Signals</div>
                      {(preview.signals || []).map((sig, idx) => (
                        <div key={`${sig.symbol}-${idx}`} className="flex items-center justify-between border-b border-slate-900 last:border-b-0 py-1">
                          <span className="font-semibold">{sig.symbol}</span>
                          <span className="capitalize text-slate-200">{sig.action}</span>
                          <span className="text-slate-400">conf {Number(sig.confidence || 0).toFixed(2)}</span>
                          <div className="flex gap-1 flex-wrap text-[10px] text-slate-400">
                            {Object.entries(sig.indicators || {}).map(([k, v]) => (
                              <span key={k} className="px-2 py-0.5 rounded-lg bg-slate-800 border border-slate-700">
                                {k}: {Number(v).toFixed(2)}
                              </span>
                            ))}
                          </div>
                        </div>
                      ))}
                      {!preview.signals?.length && (
                        <div className="text-slate-500 text-[11px]">No signals.</div>
                      )}
                    </div>
                    <div className="bg-slate-950 border border-slate-800 rounded-xl p-2 text-xs space-y-1">
                      <div className="font-semibold text-slate-200">Recommended orders</div>
                      {(preview.recommended_orders || []).map((ord, idx) => (
                        <div key={idx} className="flex items-center gap-2">
                          <span className="font-semibold">{ord.symbol}</span>
                          <span>{ord.side}</span>
                          <span>{ord.qty}</span>
                          <span className="text-slate-500">{ord.type}</span>
                        </div>
                      ))}
                      {!preview.recommended_orders?.length && (
                        <div className="text-slate-500 text-[11px]">No trades recommended.</div>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="text-xs text-slate-500">No preview yet.</div>
                )}
              </div>
            </div>

            <div className="space-y-3">
              <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-4 space-y-2">
                <div className="text-sm font-semibold">Forward runs</div>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead className="text-slate-400 border-b border-slate-800">
                      <tr className="text-left">
                        <th className="py-2 pr-2">As of</th>
                        <th className="py-2 pr-2">Equity</th>
                        <th className="py-2 pr-2">PnL</th>
                        <th className="py-2 pr-2">Trades</th>
                      </tr>
                    </thead>
                    <tbody>
                      {forwardRuns.map((run) => (
                        <tr key={run.id} className="border-t border-slate-900">
                          <td className="py-1 pr-2">
                            {run.as_of ? new Date(run.as_of).toLocaleDateString() : "—"}
                          </td>
                          <td className="py-1 pr-2 text-emerald-200">
                            ${Number(run.equity || 0).toLocaleString()}
                          </td>
                          <td className="py-1 pr-2 text-slate-200">{Number(run.pnl || 0).toFixed(2)}</td>
                          <td className="py-1 pr-2">{run.num_trades}</td>
                        </tr>
                      ))}
                      {!forwardRuns.length && (
                        <tr>
                          <td colSpan={4} className="py-2 text-center text-slate-500">
                            No forward runs yet.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-4 space-y-2">
                <div className="text-sm font-semibold">Recent orders</div>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead className="text-slate-400 border-b border-slate-800">
                      <tr className="text-left">
                        <th className="py-2 pr-2">Symbol</th>
                        <th className="py-2 pr-2">Side</th>
                        <th className="py-2 pr-2">Type</th>
                        <th className="py-2 pr-2">Qty</th>
                        <th className="py-2 pr-2">Status</th>
                        <th className="py-2 pr-2">Filled</th>
                        <th className="py-2 pr-2 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {orders.map((o) => (
                        <tr key={o.id} className="border-t border-slate-900">
                          <td className="py-1 pr-2">{o.symbol}</td>
                          <td className="py-1 pr-2">{o.side}</td>
                          <td className="py-1 pr-2">{o.order_type}</td>
                          <td className="py-1 pr-2">{o.quantity || o.notional || "—"}</td>
                          <td className="py-1 pr-2">{o.status}</td>
                          <td className="py-1 pr-2">
                            {o.average_fill_price ? `$${o.average_fill_price}` : "—"}
                          </td>
                          <td className="py-1 pr-2 text-right">
                            {["new", "working", "part_filled"].includes(o.status) && (
                              <button
                                type="button"
                                onClick={() => handleCheckFill(o.id)}
                                className="btn-secondary text-[11px] px-2 py-1 disabled:opacity-60"
                                disabled={simulatingId === o.id}
                              >
                                {simulatingId === o.id ? "Checking…" : "Check fill"}
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                      {!orders.length && (
                        <tr>
                          <td colSpan={7} className="py-2 text-center text-slate-500">
                            No recent orders for this bot.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>

          <div className="grid lg:grid-cols-2 gap-4">
            <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-4">
              <div className="text-sm font-semibold mb-2">Strategy spec (read-only)</div>
              <pre className="text-[11px] bg-slate-950 border border-slate-800 rounded-xl p-3 overflow-auto max-h-80">
                {bot?.strategy_spec_data ? JSON.stringify(bot.strategy_spec_data, null, 2) : "No strategy spec attached."}
              </pre>
            </div>
            <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-4">
              <div className="text-sm font-semibold mb-2">Bot config (read-only)</div>
              <pre className="text-[11px] bg-slate-950 border border-slate-800 rounded-xl p-3 overflow-auto max-h-80">
                {bot?.bot_config_data ? JSON.stringify(bot.bot_config_data, null, 2) : "No bot config attached."}
              </pre>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
