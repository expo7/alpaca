// [NOTE-WATCHLIST-PAGE]
// Minimal CRUD + "Use in Ranker" action
import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../AuthProvider.jsx";
import AlertHistoryPanel from "../components/AlertHistoryPanel";
import InstrumentSearch from "../components/InstrumentSearch.jsx";

const BASE = "http://127.0.0.1:8000";

async function apiFetch(path, { token, ...opts }) {
  const headers = { ...(opts.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${BASE}${path}`, { ...opts, headers });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(JSON.stringify(json || { status: res.status }));
  return json;
}

export default function Watchlists({ onUseTickers }) {
  const { token } = useAuth();
  const [lists, setLists] = useState([]);
  const [name, setName] = useState("");
  const [addById, setAddById] = useState(null);
  const [symbol, setSymbol] = useState("");
  const [err, setErr] = useState("");

  const load = useCallback(async () => {
    setErr("");
    try {
      const json = await apiFetch(`/api/watchlists/`, { token });
      setLists(json);
    } catch (e) {
      setErr(String(e));
    }
  }, [token]);

  useEffect(() => { load(); }, [load]);

  async function createList() {
    if (!name.trim()) return;
    setErr("");
    try {
      await apiFetch(`/api/watchlists/`, {
        token, method: "POST", headers: { "Content-Type":"application/json" },
        body: JSON.stringify({ name: name.trim() })
      });
      setName("");
      load();
    } catch (e) { setErr(String(e)); }
  }

  async function deleteList(id) {
    setErr("");
    try {
      await apiFetch(`/api/watchlists/${id}/`, { token, method: "DELETE" });
      load();
    } catch (e) { setErr(String(e)); }
  }

  async function addItem(id) {
    if (!symbol.trim()) return;
    setErr("");
    try {
      await apiFetch(`/api/watchlists/${id}/items/`, {
        token, method: "POST", headers: { "Content-Type":"application/json" },
        body: JSON.stringify({ symbol: symbol.trim().toUpperCase() })
      });
      setSymbol("");
      setAddById(null);
      load();
    } catch (e) { setErr(String(e)); }
  }

  async function removeItem(wid, itemId) {
    setErr("");
    try {
      await apiFetch(`/api/watchlists/${wid}/items/${itemId}/`, { token, method: "DELETE" });
      load();
    } catch (e) { setErr(String(e)); }
  }

  return (
    <div className="space-y-4">
      <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-4">
        <div className="text-lg font-semibold">Watchlists</div>
        <div className="mt-3 flex gap-2">
          <input
            value={name}
            onChange={(e)=>setName(e.target.value)}
            placeholder="New watchlist name"
            className="bg-slate-950 border border-slate-800 rounded-xl p-2 flex-1"
          />
          <button onClick={createList} className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500">Create</button>
        </div>
        {err && <div className="mt-3 text-rose-300 text-sm">{err}</div>}
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        {lists.map((wl) => (
          <div key={wl.id} className="bg-slate-900/50 border border-slate-800 rounded-2xl p-4">
            <div className="flex items-center justify-between">
              <div className="font-semibold">{wl.name}</div>
              <div className="flex gap-2">
                <button
                  onClick={()=>onUseTickers?.(wl.items.map(i=>i.symbol))}
                  className="px-3 py-1.5 rounded-lg border border-slate-700 hover:bg-slate-800 text-sm"
                >
                  Use in Ranker
                </button>
                <button
                  onClick={()=>deleteList(wl.id)}
                  className="px-3 py-1.5 rounded-lg border border-rose-900 text-rose-200 hover:bg-rose-950 text-sm"
                >
                  Delete
                </button>
              </div>
            </div>

            <div className="mt-3">
              <div className="text-xs text-slate-400 mb-2">Symbols</div>
              <div className="flex flex-wrap gap-2">
                {wl.items.map((it) => (
                  <span key={it.id} className="inline-flex items-center gap-2 px-2 py-1 rounded-lg bg-slate-800 border border-slate-700">
                    {it.symbol}
                    <button
                      onClick={()=>removeItem(wl.id, it.id)}
                      className="text-slate-400 hover:text-white"
                      title="Remove"
                    >×</button>
                  </span>
                ))}
                {!wl.items?.length && <span className="text-slate-500 text-sm">Empty</span>}
              </div>

              {/* Add symbol */}
              {addById === wl.id ? (
                <div className="mt-3 flex flex-col gap-2">
                  <div className="flex gap-2">
                    <input
                      value={symbol}
                      onChange={(e)=>setSymbol(e.target.value)}
                      placeholder="e.g., AAPL"
                      className="bg-slate-950 border border-slate-800 rounded-xl p-2 flex-1"
                    />
                    <button onClick={()=>addItem(wl.id)} className="px-3 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500">Add</button>
                    <button onClick={()=>setAddById(null)} className="px-3 py-2 rounded-xl border border-slate-700 hover:bg-slate-900">Cancel</button>
                  </div>
                  <InstrumentSearch onSelect={(sym)=>setSymbol(sym)} />
                </div>
              ) : (
                <div className="mt-3">
                  <button onClick={()=>setAddById(wl.id)} className="px-3 py-1.5 rounded-xl border border-slate-700 hover:bg-slate-900 text-sm">
                    + Add symbol
                  </button>
                </div>
              )}
            </div>
          </div>
        ))}
        {!lists.length && (
          <div className="text-slate-500 text-sm">No watchlists yet — create one above.</div>
        )}
      </div>
    </div>
  );
}
