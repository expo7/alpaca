import { useEffect, useState } from "react";
import { useAuth } from "../AuthProvider.jsx";
import { fetchBots, startBot, pauseBot, stopBot, fetchConfig, fetchBotForwardRuns, previewBot } from "../api/bots.js";

function stateBadge(state) {
  const common = "px-2 py-1 rounded-full text-[11px] font-semibold";
  if (state === "running") return `${common} bg-emerald-500/20 text-emerald-200 border border-emerald-600/40`;
  if (state === "paused") return `${common} bg-amber-500/20 text-amber-100 border border-amber-600/40`;
  return `${common} bg-slate-800 text-slate-200 border border-slate-700`;
}

function modeBadge(mode) {
  const common = "px-2 py-1 rounded-full text-[11px] font-semibold border";
  if (mode === "live") {
    return `${common} bg-rose-600/20 text-rose-200 border-rose-500`;
  }
  return `${common} bg-slate-800 text-slate-200 border-slate-700`;
}

export default function BotsPage({ onSelectBot }) {
  const { token } = useAuth();
  const handleSelect = onSelectBot || (() => {});
  const [bots, setBots] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [config, setConfig] = useState({ allow_live_bots: false });
  const [liveModal, setLiveModal] = useState({
    open: false,
    bot: null,
    confirmed: false,
    confirmText: "",
    error: "",
  });
  const [forwardModal, setForwardModal] = useState({
    open: false,
    bot: null,
    runs: [],
    loading: false,
    error: "",
  });
  const [previewModal, setPreviewModal] = useState({
    open: false,
    bot: null,
    loading: false,
    error: "",
    data: null,
  });

  async function loadBots() {
    setLoading(true);
    setError("");
    try {
      const data = await fetchBots(token);
      setBots(Array.isArray(data) ? data : []);
    } catch (e) {
      setError(e.message || "Failed to load bots");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!token) return;
    loadBots();
    fetchConfig(token)
      .then((cfg) => setConfig(cfg))
      .catch(() => setConfig({ allow_live_bots: false }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function handleAction(botId, action) {
    setActionError("");
    try {
      let updated;
      if (action === "start") {
        updated = await startBot(botId, token);
      } else if (action === "pause") {
        updated = await pauseBot(botId, token);
      } else if (action === "stop") {
        updated = await stopBot(botId, token);
      }
      setBots((prev) => prev.map((b) => (b.id === botId ? updated : b)));
    } catch (e) {
      setActionError(e.message || `Failed to ${action}`);
    }
  }

  function handleStart(bot) {
    if (bot.mode === "live") {
      setLiveModal({
        open: true,
        bot,
        confirmed: false,
        confirmText: "",
        error: "",
      });
      return;
    }
    handleAction(bot.id, "start");
  }

  function closeLiveModal() {
    setLiveModal({ open: false, bot: null, confirmed: false, confirmText: "", error: "" });
  }

  async function openForwardHistory(bot) {
    if (!bot) return;
    setForwardModal({ open: true, bot, runs: [], loading: true, error: "" });
    try {
      const runs = await fetchBotForwardRuns(bot.id, token);
      setForwardModal((m) => ({ ...m, runs, loading: false }));
    } catch (err) {
      setForwardModal((m) => ({
        ...m,
        loading: false,
        error: err.message || "Failed to load forward runs",
      }));
    }
  }

  async function openPreview(bot) {
    if (!bot) return;
    setPreviewModal({ open: true, bot, loading: true, error: "", data: null });
    try {
      const data = await previewBot(bot.id, token);
      setPreviewModal((m) => ({ ...m, loading: false, data }));
    } catch (err) {
      setPreviewModal((m) => ({
        ...m,
        loading: false,
        error: err.message || "Failed to preview signals",
      }));
    }
  }

  async function confirmLiveStart() {
    if (!liveModal.bot) return;
    try {
      const updated = await startBot(liveModal.bot.id, token);
      setBots((prev) => prev.map((b) => (b.id === liveModal.bot.id ? updated : b)));
      closeLiveModal();
    } catch (e) {
      setLiveModal((m) => ({ ...m, error: e.message || "Failed to start live bot" }));
    }
  }

  return (
    <>
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-lg font-semibold">Bots</div>
            <div className="text-sm text-slate-400">Start, pause, or stop your bots.</div>
          </div>
          <button
            type="button"
            onClick={loadBots}
            className="btn-secondary"
            disabled={loading}
          >
            {loading ? "Refreshing..." : "Refresh"}
          </button>
        </div>

        {!config.allow_live_bots && (
          <div className="text-xs text-amber-200 bg-amber-900/30 border border-amber-700 rounded-xl p-3">
            Live trading is disabled in this environment. Live bots cannot be started.
          </div>
        )}

        {error && (
          <div className="text-xs text-rose-300 bg-rose-900/40 border border-rose-800 rounded-xl p-3">
            {error}
          </div>
        )}
        {actionError && (
          <div className="text-xs text-amber-200 bg-amber-900/30 border border-amber-700 rounded-xl p-3">
            {actionError}
          </div>
        )}

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-slate-400 border-b border-slate-800">
              <tr className="text-left">
                <th className="py-2 pr-2">Name</th>
                <th className="py-2 pr-2">Symbols</th>
                <th className="py-2 pr-2">Mode</th>
                <th className="py-2 pr-2">State</th>
                <th className="py-2 pr-2">Schedule</th>
                <th className="py-2 pr-2">Rebalance</th>
                <th className="py-2 pr-2">Last forward</th>
                <th className="py-2 pr-2">Last run</th>
                <th className="py-2 pr-2">Next run</th>
                <th className="py-2 pr-2 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {bots.map((bot) => (
                <tr key={bot.id} className="border-t border-slate-900 hover:bg-slate-900/40">
                  <td className="py-2 pr-2 font-semibold">{bot.name || `Bot ${bot.id}`}</td>
                  <td className="py-2 pr-2 text-slate-300">
                    {(bot.symbols || []).join(", ")}
                  </td>
                  <td className="py-2 pr-2">
                    <span className={modeBadge(bot.mode)}>{bot.mode}</span>
                  </td>
                  <td className="py-2 pr-2">
                    <span className={stateBadge(bot.state)}>{bot.state}</span>
                  </td>
                  <td className="py-2 pr-2 text-slate-300">{bot.schedule}</td>
                  <td className="py-2 pr-2 text-slate-300">
                    {bot.rebalance_days ?? bot.config?.rebalance_days ?? "—"}
                  </td>
                  <td className="py-2 pr-2 text-slate-300">
                    {bot.last_forward_run_at
                      ? new Date(bot.last_forward_run_at).toLocaleDateString()
                      : "—"}
                  </td>
                  <td className="py-2 pr-2 text-slate-400 text-xs">
                    {bot.last_run_at ? new Date(bot.last_run_at).toLocaleString() : "-"}
                  </td>
                  <td className="py-2 pr-2 text-slate-400 text-xs">
                    {bot.next_run_at ? new Date(bot.next_run_at).toLocaleString() : "-"}
                  </td>
                  <td className="py-2 pr-2">
                    <div className="flex justify-end gap-2">
                      <button
                        type="button"
                        onClick={() => handleSelect(bot.id)}
                        className="btn-secondary"
                        onClickCapture={(e) => e.stopPropagation()}
                      >
                        View
                      </button>
                      <button
                        type="button"
                        onClick={() => handleStart(bot)}
                        disabled={
                          bot.state === "running" ||
                          (bot.mode === "live" && !config.allow_live_bots)
                        }
                        className="btn-primary disabled:opacity-50"
                      >
                        Start
                      </button>
                      <button
                        type="button"
                        onClick={() => handleAction(bot.id, "pause")}
                        disabled={bot.state === "paused" || bot.state === "stopped"}
                        className="btn-secondary disabled:opacity-50"
                      >
                        Pause
                      </button>
                      <button
                        type="button"
                        onClick={() => handleAction(bot.id, "stop")}
                        disabled={bot.state === "stopped"}
                        className="btn-secondary disabled:opacity-50"
                    >
                      Stop
                    </button>
                      <button
                        type="button"
                        onClick={() => openPreview(bot)}
                        className="btn-secondary"
                      >
                        Preview signals
                      </button>
                      <button
                        type="button"
                        onClick={() => openForwardHistory(bot)}
                        className="btn-secondary"
                      >
                        Forward history
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            {!bots.length && !loading && (
              <tr>
                <td colSpan={10} className="py-4 text-center text-slate-500">
                  No bots yet.
                </td>
              </tr>
            )}
          </tbody>
          </table>
        </div>
      </div>
      {liveModal.open && liveModal.bot && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-slate-950 border border-slate-800 rounded-2xl p-4 w-full max-w-md space-y-3">
            <div className="text-lg font-semibold text-rose-200">Confirm LIVE start</div>
            <div className="text-xs text-slate-300">
              Bot: <span className="font-semibold">{liveModal.bot.name || `Bot ${liveModal.bot.id}`}</span>
            </div>
            <div className="text-xs text-slate-300">
              Mode: <span className="font-semibold text-rose-300">LIVE</span>
            </div>
            <div className="text-xs text-slate-300">
              Symbols: {(liveModal.bot.symbols || []).join(", ")}
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={liveModal.confirmed}
                onChange={(e) =>
                  setLiveModal((m) => ({ ...m, confirmed: e.target.checked }))
                }
              />
              <span>I understand this bot will place LIVE orders.</span>
            </label>
            <label className="flex flex-col gap-1 text-xs">
              <span>Type LIVE to confirm</span>
              <input
                value={liveModal.confirmText}
                onChange={(e) =>
                  setLiveModal((m) => ({ ...m, confirmText: e.target.value }))
                }
                className="bg-slate-900 border border-slate-800 rounded-lg p-2"
              />
            </label>
            {liveModal.error && (
              <div className="text-xs text-rose-300">{liveModal.error}</div>
            )}
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={closeLiveModal}
                className="btn-secondary"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={
                  !liveModal.confirmed || liveModal.confirmText.trim().toUpperCase() !== "LIVE"
                }
                onClick={confirmLiveStart}
                className="btn-primary disabled:opacity-50"
              >
                Confirm & Start
              </button>
            </div>
          </div>
        </div>
      )}
      {forwardModal.open && forwardModal.bot && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-slate-950 border border-slate-800 rounded-2xl p-4 w-full max-w-2xl space-y-3">
            <div className="flex items-center justify-between">
              <div className="text-lg font-semibold text-slate-100">
                Forward history · {forwardModal.bot.name || `Bot ${forwardModal.bot.id}`}
              </div>
              <button
                type="button"
                onClick={() => setForwardModal({ open: false, bot: null, runs: [], loading: false, error: "" })}
                className="text-slate-300 hover:text-white"
              >
                ✕
              </button>
            </div>
            {forwardModal.loading && (
              <div className="text-xs text-slate-300">Loading forward runs…</div>
            )}
            {forwardModal.error && (
              <div className="text-xs text-rose-300">{forwardModal.error}</div>
            )}
            {!forwardModal.loading && !forwardModal.error && (
              <div className="space-y-3">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="text-slate-400 border-b border-slate-800">
                      <tr className="text-left">
                        <th className="py-2 pr-2">As of</th>
                        <th className="py-2 pr-2">Equity</th>
                        <th className="py-2 pr-2">Cash</th>
                        <th className="py-2 pr-2">PnL</th>
                        <th className="py-2 pr-2">Trades</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(forwardModal.runs || []).map((run) => (
                        <tr key={run.id} className="border-t border-slate-900">
                          <td className="py-1 pr-2 text-xs">
                            {run.as_of ? new Date(run.as_of).toLocaleDateString() : "—"}
                          </td>
                          <td className="py-1 pr-2 text-xs text-emerald-200">
                            ${Number(run.equity || 0).toLocaleString()}
                          </td>
                          <td className="py-1 pr-2 text-xs text-slate-300">
                            ${Number(run.cash || 0).toLocaleString()}
                          </td>
                          <td className="py-1 pr-2 text-xs text-slate-200">
                            {Number(run.pnl || 0).toFixed(2)}
                          </td>
                          <td className="py-1 pr-2 text-xs">{run.num_trades}</td>
                        </tr>
                      ))}
                      {!forwardModal.runs.length && (
                        <tr>
                          <td colSpan={5} className="py-2 text-center text-slate-500 text-xs">
                            No forward runs yet.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
      {previewModal.open && previewModal.bot && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-slate-950 border border-slate-800 rounded-2xl p-4 w-full max-w-3xl space-y-3">
            <div className="flex items-center justify-between">
              <div className="text-lg font-semibold text-slate-100">
                Preview signals · {previewModal.bot.name || `Bot ${previewModal.bot.id}`}
              </div>
              <button
                type="button"
                onClick={() => setPreviewModal({ open: false, bot: null, data: null, loading: false, error: "" })}
                className="text-slate-300 hover:text-white"
              >
                ✕
              </button>
            </div>
            {previewModal.loading && <div className="text-xs text-slate-300">Fetching preview…</div>}
            {previewModal.error && <div className="text-xs text-rose-300">{previewModal.error}</div>}
            {previewModal.data && (
              <div className="space-y-3">
                <div className="text-sm text-slate-300">
                  Would trade?{" "}
                  <span className={previewModal.data.would_trade ? "text-emerald-300" : "text-slate-400"}>
                    {previewModal.data.would_trade ? "Yes" : "No"}
                  </span>
                </div>
                <div className="grid md:grid-cols-2 gap-3">
                  <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-3">
                    <div className="text-sm font-semibold mb-2">Signals</div>
                    {(previewModal.data.signals || []).map((sig) => (
                      <div key={`${sig.symbol}-${sig.action}`} className="border-b border-slate-800 py-2 last:border-b-0">
                        <div className="flex items-center justify-between text-xs">
                          <span className="font-semibold text-slate-100">{sig.symbol}</span>
                          <span className="text-slate-300 capitalize">{sig.action}</span>
                          <span className="text-[11px] text-slate-400">conf {Number(sig.confidence || 0).toFixed(2)}</span>
                        </div>
                        <div className="text-[11px] text-slate-400 flex flex-wrap gap-2 mt-1">
                          {Object.entries(sig.indicators || {}).map(([k, v]) => (
                            <span key={k} className="px-2 py-0.5 rounded-lg bg-slate-800 border border-slate-700">
                              {k}: {Number(v).toFixed(2)}
                            </span>
                          ))}
                        </div>
                      </div>
                    ))}
                    {!previewModal.data.signals?.length && (
                      <div className="text-xs text-slate-500">No signals.</div>
                    )}
                  </div>
                  <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-3 space-y-2">
                    <div className="text-sm font-semibold">Recommended orders</div>
                    {(previewModal.data.recommended_orders || []).map((ord, idx) => (
                      <div key={idx} className="text-xs text-slate-300 flex items-center gap-2">
                        <span className="font-semibold">{ord.symbol}</span>
                        <span>{ord.side}</span>
                        <span>{ord.qty}</span>
                        <span className="text-slate-500">{ord.type}</span>
                      </div>
                    ))}
                    {!previewModal.data.recommended_orders?.length && (
                      <div className="text-xs text-slate-500">No trades recommended.</div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
