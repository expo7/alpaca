import { useState } from "react";

const BASE = "http://127.0.0.1:8000";

export default function InstrumentSearch({ onSelect }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);

  const search = async () => {
    if (!query.trim()) return;
    setLoading(true);
    try {
      const res = await fetch(
        `${BASE}/api/paper/instruments/?q=${encodeURIComponent(query)}`
      );
      if (!res.ok) throw new Error("Lookup failed");
      const data = await res.json();
      setResults(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-slate-950 border border-slate-800 rounded-xl p-3 space-y-2 text-xs">
      <div className="flex gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Lookup symbol…"
          className="flex-1 bg-slate-900 border border-slate-800 rounded-lg px-2 py-1.5"
        />
        <button
          type="button"
          onClick={search}
          className="px-3 py-1.5 rounded-lg border border-slate-700"
        >
          {loading ? "…" : "Search"}
        </button>
      </div>
      {results.length > 0 && (
        <div className="max-h-32 overflow-auto border border-slate-800 rounded-lg">
          {results.map((inst) => (
            <button
              key={inst.id || inst.symbol}
              type="button"
              className="w-full text-left px-3 py-1.5 hover:bg-slate-800 flex justify-between"
              onClick={() => onSelect?.(inst.symbol)}
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
  );
}
