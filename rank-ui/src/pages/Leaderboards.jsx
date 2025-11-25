import { useEffect, useMemo, useState } from "react";
import { useAuth } from "../AuthProvider.jsx";

const BASE = "http://127.0.0.1:8000";
const METRICS = [
  { id: "return_pct", label: "Return %" },
  { id: "sharpe", label: "Sharpe" },
  { id: "consistency", label: "Consistency" },
];

async function apiFetch(path, { token, ...opts } = {}) {
  const headers = { ...(opts.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${BASE}${path}`, { ...opts, headers });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data?.detail || JSON.stringify(data));
  }
  return data;
}

export default function Leaderboards() {
  const { token } = useAuth();
  const authed = Boolean(token);
  const [entries, setEntries] = useState([]);
  const [seasons, setSeasons] = useState([]);
  const [season, setSeason] = useState("");
  const [metric, setMetric] = useState("return_pct");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token) return;
    (async () => {
      try {
        const data = await apiFetch("/api/paper/leaderboards/seasons/", {
          token,
        });
        setSeasons(data);
        if (!season && data.length) {
          setSeason(String(data[0].id));
        }
      } catch (err) {
        console.error(err);
      }
    })();
  }, [token, season]);

  useEffect(() => {
    if (!token) return;
    setLoading(true);
    setError("");
    (async () => {
      try {
        const searchParams = new URLSearchParams({ metric });
        if (season) searchParams.append("season", season);
        const data = await apiFetch(
          `/api/paper/leaderboards/entries/?${searchParams.toString()}`,
          { token }
        );
        setEntries(Array.isArray(data) ? data : []);
      } catch (err) {
        console.error(err);
        setError("Failed to load leaderboard entries");
      } finally {
        setLoading(false);
      }
    })();
  }, [token, metric, season]);

  const seasonMap = useMemo(() => {
    const map = {};
    seasons.forEach((s) => {
      map[String(s.id)] = s.name;
    });
    return map;
  }, [seasons]);

  if (!authed) {
    return (
      <div className="p-4 text-sm text-amber-300">
        Login required to view leaderboards.
      </div>
    );
  }

  return (
    <div className="p-4 lg:p-6 space-y-4">
      <div className="flex flex-wrap items-center gap-3 justify-between">
        <div>
          <h1 className="text-lg font-semibold">Leaderboards</h1>
          <p className="text-sm text-slate-400">
            Compare paper accounts by performance.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <select
            value={season}
            onChange={(e) => setSeason(e.target.value)}
            className="bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-sm"
          >
            <option value="">All seasons</option>
            {seasons.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
          <select
            value={metric}
            onChange={(e) => setMetric(e.target.value)}
            className="bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-sm"
          >
            {METRICS.map((m) => (
              <option key={m.id} value={m.id}>
                {m.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {error && (
        <div className="text-xs text-rose-200 bg-rose-900/30 border border-rose-800 rounded-xl px-3 py-2">
          {error}
        </div>
      )}

      <div className="bg-slate-900/50 border border-slate-800 rounded-2xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="text-slate-400 text-xs bg-slate-900/60">
            <tr>
              <th className="px-3 py-2 text-left">Rank</th>
              <th className="px-3 py-2 text-left">Portfolio</th>
              <th className="px-3 py-2 text-left">Metric</th>
              <th className="px-3 py-2 text-left">Period</th>
              <th className="px-3 py-2 text-left">Season</th>
              <th className="px-3 py-2 text-left">Updated</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry) => (
              <tr key={entry.id} className="border-t border-slate-800 text-xs">
                <td className="px-3 py-2 font-semibold">{entry.rank}</td>
                <td className="px-3 py-2">
                  <div className="font-medium">
                    {entry.portfolio?.name || "Portfolio"}
                  </div>
                  <div className="text-[11px] text-slate-500">
                    {entry.portfolio?.base_currency}
                  </div>
                </td>
                <td className="px-3 py-2">
                  {Number(entry.value).toFixed(2)}{" "}
                  <span className="text-slate-500">{entry.metric}</span>
                </td>
                <td className="px-3 py-2">{entry.period}</td>
                <td className="px-3 py-2">
                  {seasonMap[String(entry.season)] || "—"}
                </td>
                <td className="px-3 py-2">
                  {new Date(entry.calculated_at).toLocaleDateString()}
                </td>
              </tr>
            ))}
            {!entries.length && (
              <tr>
                <td
                  className="px-3 py-4 text-center text-slate-500"
                  colSpan={6}
                >
                  {loading ? "Loading..." : "No entries yet."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
