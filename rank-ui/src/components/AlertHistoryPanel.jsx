// src/components/AlertHistoryPanel.jsx
import React, { useEffect, useState } from "react";
import { useAuth } from "../AuthProvider.jsx"; // <-- use the shared auth context

const BASE = "http://127.0.0.1:8000"; // same as App.jsx

export default function AlertHistoryPanel() {
    const { token } = useAuth(); // <-- same token Alerts page uses

    const [events, setEvents] = useState([]);
    const [symbolFilter, setSymbolFilter] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [initialized, setInitialized] = useState(false);

    async function fetchHistory(params = {}) {
        if (!token) {
            setError("You must be logged in to view alert history.");
            setEvents([]);
            return;
        }

        try {
            setLoading(true);
            setError("");

            const query = new URLSearchParams();
            if (params.symbol) {
                query.set("symbol", params.symbol);
            }

            const url =
                query.toString().length > 0
                    ? `${BASE}/api/alert-events/?${query.toString()}`
                    : `${BASE}/api/alert-events/`;

            const res = await fetch(url, {
                headers: {
                    Authorization: `Bearer ${token}`,
                },
            });

            const text = await res.text(); // <-- read raw body for logging + parsing
            console.log("alert-events response:", res.status, text);

            let data = null;
            try {
                data = text ? JSON.parse(text) : null;
            } catch {
                data = null;
            }

            if (!res.ok) {
                // pull out typical DRF error fields if present
                const detail =
                    (data && (data.detail || data.error)) ||
                    text ||
                    `HTTP ${res.status}`;
                throw new Error(detail);
            }

            // success
            const results = (data && data.results) || data || [];
            setEvents(results);
            setInitialized(true);
        } catch (err) {
            console.error("Failed to fetch alert history", err);
            setError(`Failed to load alert history: ${err.message}`);
        } finally {
            setLoading(false);
        }
    }


    //   async function fetchHistory(params = {}) {
    //     if (!token) {
    //       setError("You must be logged in to view alert history.");
    //       setEvents([]);
    //       return;
    //     }

    //     try {
    //       setLoading(true);
    //       setError("");

    //       const query = new URLSearchParams();
    //       if (params.symbol) {
    //         query.set("symbol", params.symbol);
    //       }

    //       const url =
    //         query.toString().length > 0
    //           ? `${BASE}/api/alert-events/?${query.toString()}`
    //           : `${BASE}/api/alert-events/`;

    //       const res = await fetch(url, {
    //         headers: {
    //           Authorization: `Bearer ${token}`,
    //         },
    //       });

    //       if (!res.ok) {
    //         throw new Error(`HTTP ${res.status}`);
    //       }

    //       const data = await res.json();
    //       setEvents(data.results || []);
    //       setInitialized(true);
    //     } catch (err) {
    //       console.error("Failed to fetch alert history", err);
    //       setError("Failed to load alert history. Check your token / server.");
    //     } finally {
    //       setLoading(false);
    //     }
    //   }

    // initial load + refetch when token changes
    useEffect(() => {
        if (!token) {
            setError("You must be logged in to view alert history.");
            setEvents([]);
            return;
        }
        fetchHistory({});
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [token]);

    function handleApplyFilter(e) {
        e.preventDefault();
        const sym = symbolFilter.trim();
        fetchHistory(sym ? { symbol: sym } : {});
    }

    function resetFilter() {
        setSymbolFilter("");
        fetchHistory({});
    }

    return (
        <section className="mt-10">
            {/* ALERT HISTORY HEADER */}
            <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 mb-4">
                <div>
                    <h2 className="text-lg font-semibold text-slate-100">
                        Alert History
                    </h2>
                    <p className="text-xs text-slate-400 mt-1">
                        See when your alerts actually fired, with scores at the time.
                    </p>
                </div>

                {/* FILTER BAR */}
                <form
                    onSubmit={handleApplyFilter}
                    className="flex flex-wrap items-center gap-2"
                >
                    <input
                        type="text"
                        value={symbolFilter}
                        onChange={(e) => setSymbolFilter(e.target.value.toUpperCase())}
                        placeholder="Filter by symbol (e.g. TNXP)"
                        className="px-3 py-1.5 rounded-md bg-slate-900 border border-slate-700 text-xs text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                    />
                    <button
                        type="submit"
                        className="px-3 py-1.5 text-xs rounded-md bg-indigo-600 hover:bg-indigo-500 text-white"
                    >
                        Apply
                    </button>
                    <button
                        type="button"
                        onClick={resetFilter}
                        className="px-3 py-1.5 text-xs rounded-md border border-slate-600 text-slate-200 hover:bg-slate-800"
                    >
                        Reset
                    </button>
                </form>
            </div>

            {/* STATUS / ERRORS */}
            {error && (
                <div className="mb-3 text-xs text-red-400 bg-red-950/40 border border-red-800 rounded-md px-3 py-2">
                    {error}
                </div>
            )}

            {/* TABLE / EMPTY / LOADING */}
            <div className="rounded-xl border border-slate-800 bg-slate-950/60 overflow-hidden">
                {loading && (
                    <div className="p-6 text-sm text-slate-300">
                        Loading alert history…
                    </div>
                )}

                {!loading && initialized && events.length === 0 && (
                    <div className="p-6 text-sm text-slate-400">
                        No alert events yet. Once your alerts fire, they&apos;ll appear
                        here.
                    </div>
                )}

                {!loading && events.length > 0 && (
                    <div className="overflow-x-auto">
                        <table className="min-w-full text-xs text-slate-200">
                            <thead className="bg-slate-900/80">
                                <tr>
                                    <th className="px-3 py-2 text-left font-medium text-slate-400">
                                        Time
                                    </th>
                                    <th className="px-3 py-2 text-left font-medium text-slate-400">
                                        Symbol
                                    </th>
                                    <th className="px-3 py-2 text-right font-medium text-slate-400">
                                        Final
                                    </th>
                                    <th className="px-3 py-2 text-right font-medium text-slate-400">
                                        Tech
                                    </th>
                                    <th className="px-3 py-2 text-right font-medium text-slate-400">
                                        Fund
                                    </th>
                                    <th className="px-3 py-2 text-right font-medium text-slate-400">
                                        Alert ID
                                    </th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-800/80">
                                {events.map((evt) => (
                                    <tr key={evt.id} className="hover:bg-slate-900/40">
                                        <td className="px-3 py-2 whitespace-nowrap text-slate-300">
                                            {new Date(evt.triggered_at).toLocaleString()}
                                        </td>
                                        <td className="px-3 py-2 font-semibold text-slate-100">
                                            {evt.symbol}
                                        </td>
                                        <td className="px-3 py-2 text-right">
                                            {Number(evt.final_score).toFixed(2)}
                                        </td>
                                        <td className="px-3 py-2 text-right text-sky-300">
                                            {Number(evt.tech_score).toFixed(2)}
                                        </td>
                                        <td className="px-3 py-2 text-right text-emerald-300">
                                            {Number(evt.fund_score).toFixed(2)}
                                        </td>
                                        <td className="px-3 py-2 text-right text-slate-400">
                                            #{evt.alert_id}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </section>
    );
}
