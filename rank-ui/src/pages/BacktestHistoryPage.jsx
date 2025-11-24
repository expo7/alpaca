import { useEffect, useState } from "react";
import { useAuth } from "../AuthProvider.jsx";
import { fetchBatchList, fetchBatchDetail } from "../api/batches.js";

export default function BacktestHistoryPage() {
  const { token } = useAuth();
  const [batches, setBatches] = useState([]);
  const [selectedId, setSelectedId] = useState("");
  const [selectedDetail, setSelectedDetail] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [detailError, setDetailError] = useState("");

  async function loadBatches() {
    setLoading(true);
    setError("");
    try {
      const data = await fetchBatchList(token);
      setBatches(Array.isArray(data) ? data : []);
    } catch (e) {
      setError(e.message || "Failed to load batches");
    } finally {
      setLoading(false);
    }
  }

  async function loadDetail(id) {
    if (!id) return;
    setDetailError("");
    try {
      const data = await fetchBatchDetail(id, token);
      setSelectedDetail(data);
    } catch (e) {
      setDetailError(e.message || "Failed to load batch");
    }
  }

  useEffect(() => {
    if (!token) return;
    loadBatches();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-lg font-semibold">Backtest History</div>
          <div className="text-sm text-slate-400">
            View your backtest batches and inspect runs.
          </div>
        </div>
        <button
          type="button"
          onClick={loadBatches}
          className="btn-secondary"
          disabled={loading}
        >
          {loading ? "Refreshing..." : "Refresh list"}
        </button>
      </div>

      {error && (
        <div className="text-xs text-rose-300 bg-rose-900/40 border border-rose-800 rounded-xl p-3">
          {error}
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-slate-400 border-b border-slate-800">
            <tr className="text-left">
              <th className="py-2 pr-2">ID</th>
              <th className="py-2 pr-2">Label</th>
              <th className="py-2 pr-2">Status</th>
              <th className="py-2 pr-2">Runs</th>
              <th className="py-2 pr-2">Created</th>
              <th className="py-2 pr-2">Updated</th>
              <th className="py-2 pr-2">Action</th>
            </tr>
          </thead>
          <tbody>
            {batches.map((b) => (
              <tr key={b.id} className="border-t border-slate-900 hover:bg-slate-900/40">
                <td className="py-2 pr-2">{b.id}</td>
                <td className="py-2 pr-2">{b.label || "-"}</td>
                <td className="py-2 pr-2">{b.status}</td>
                <td className="py-2 pr-2">{b.num_runs}</td>
                <td className="py-2 pr-2 text-xs text-slate-400">
                  {b.created_at ? new Date(b.created_at).toLocaleString() : "-"}
                </td>
                <td className="py-2 pr-2 text-xs text-slate-400">
                  {b.updated_at ? new Date(b.updated_at).toLocaleString() : "-"}
                </td>
                <td className="py-2 pr-2">
                  <button
                    type="button"
                    className="btn-primary text-xs"
                    onClick={() => {
                      setSelectedId(String(b.id));
                      loadDetail(b.id);
                    }}
                  >
                    View
                  </button>
                </td>
              </tr>
            ))}
            {!batches.length && !loading && (
              <tr>
                <td colSpan={7} className="py-4 text-center text-slate-500">
                  No batches yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-3 space-y-2">
        <div className="flex items-center gap-2 text-sm">
          <span className="font-semibold">Batch detail</span>
          <input
            value={selectedId}
            onChange={(e) => setSelectedId(e.target.value)}
            placeholder="Enter batch id"
            className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1 text-xs"
          />
          <button
            type="button"
            className="btn-secondary text-xs"
            onClick={() => loadDetail(selectedId)}
          >
            Load
          </button>
        </div>

        {detailError && (
          <div className="text-xs text-rose-300">{detailError}</div>
        )}

        {selectedDetail && (
          <div className="space-y-2 text-sm">
            <div className="flex flex-wrap gap-3 text-xs text-slate-300">
              <span>ID: {selectedDetail.id}</span>
              <span>Label: {selectedDetail.label || "-"}</span>
              <span>Status: {selectedDetail.status}</span>
              <span>Runs: {selectedDetail.num_runs}</span>
            </div>
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
                  </tr>
                </thead>
                <tbody>
                  {(selectedDetail.runs || []).map((run) => (
                    <tr key={run.index} className="border-t border-slate-900">
                      <td className="py-1.5 pr-2">{run.index}</td>
                      <td className="py-1.5 pr-2 whitespace-pre">
                        {JSON.stringify(run.params || {})}
                      </td>
                      <td className="py-1.5 pr-2">{run.status}</td>
                      <td className="py-1.5 pr-2">
                        {run.stats?.return_pct ?? run.stats?.total_return ?? "-"}
                      </td>
                      <td className="py-1.5 pr-2">
                        {run.stats?.max_drawdown_pct ?? run.stats?.max_drawdown ?? "-"}
                      </td>
                      <td className="py-1.5 pr-2">{run.stats?.sharpe_ratio ?? "-"}</td>
                      <td className="py-1.5 pr-2 text-rose-300">{run.error || "-"}</td>
                    </tr>
                  ))}
                  {(!selectedDetail.runs || !selectedDetail.runs.length) && (
                    <tr>
                      <td colSpan={7} className="py-3 text-center text-slate-500">
                        No runs for this batch.
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
  );
}
