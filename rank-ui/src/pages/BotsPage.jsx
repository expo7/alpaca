import { useEffect, useState } from "react";
import { useAuth } from "../AuthProvider.jsx";
import { fetchBots, startBot, pauseBot, stopBot, fetchConfig } from "../api/bots.js";

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

export default function BotsPage() {
  const { token } = useAuth();
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
                  </div>
                </td>
              </tr>
            ))}
            {!bots.length && !loading && (
              <tr>
                <td colSpan={8} className="py-4 text-center text-slate-500">
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
  );
}
