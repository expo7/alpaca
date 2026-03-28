import { useEffect, useState } from "react";
import { useAuth } from "../AuthProvider.jsx";
import { getMacroDashboard } from "../api/macro.js";
import RegimeCard from "../components/macro/RegimeCard.jsx";
import ScoreCard from "../components/macro/ScoreCard.jsx";
import SignalTable from "../components/macro/SignalTable.jsx";
import NarrativePanel from "../components/macro/NarrativePanel.jsx";
import PlaybookPanel from "../components/macro/PlaybookPanel.jsx";
import OptionsEnginePanel from "../components/macro/OptionsEnginePanel.jsx";

const MIN_LOADING_MS = 300;

function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForMinimum(startedAt) {
    const elapsed = Date.now() - startedAt;
    if (elapsed < MIN_LOADING_MS) {
        await sleep(MIN_LOADING_MS - elapsed);
    }
}

export default function MacroDashboardPage() {
    const { token } = useAuth();
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [data, setData] = useState(null);
    const [riskTolerance, setRiskTolerance] = useState("moderate");
    const [positionContext, setPositionContext] = useState("flat");
    const [ivContext, setIvContext] = useState("normal");
    const [reloadKey, setReloadKey] = useState(0);

    useEffect(() => {
        if (!token) return;
        let cancelled = false;

        (async () => {
            const startedAt = Date.now();
            setLoading(true);
            setError("");
            try {
                const payload = await getMacroDashboard(token, {
                    risk_tolerance: riskTolerance,
                    position_context: positionContext,
                    iv_context: ivContext,
                });
                if (!cancelled) setData(payload);
            } catch (err) {
                if (!cancelled) setError(err.message || "Failed to load macro dashboard");
            } finally {
                await waitForMinimum(startedAt);
                if (!cancelled) setLoading(false);
            }
        })();

        return () => {
            cancelled = true;
        };
    }, [token, riskTolerance, positionContext, ivContext, reloadKey]);

    if (!token) {
        return (
            <div className="p-4 text-sm text-amber-300">
                Login required to view Market Direction.
            </div>
        );
    }

    if (loading && !data) {
        return (
            <div className="p-4 lg:p-6 space-y-4" aria-live="polite">
                <section className="bg-slate-900/50 border border-slate-800 rounded-2xl p-4 lg:p-5">
                    <div className="h-3 w-36 bg-slate-800 rounded animate-pulse" />
                    <div className="mt-3 h-8 w-64 bg-slate-800 rounded animate-pulse" />
                    <div className="mt-3 h-3 w-72 bg-slate-800 rounded animate-pulse" />
                </section>
                <section className="grid md:grid-cols-2 xl:grid-cols-4 gap-3">
                    {[0, 1, 2, 3].map((idx) => (
                        <div
                            key={`macro-card-skeleton-${idx}`}
                            className="h-28 rounded-2xl border border-slate-800 bg-slate-900/50 animate-pulse"
                        />
                    ))}
                </section>
                <section className="h-52 rounded-2xl border border-slate-800 bg-slate-900/50 animate-pulse" />
            </div>
        );
    }

    if (error && !data) {
        return (
            <div className="p-4 text-sm text-rose-300 bg-rose-900/30 border border-rose-800 rounded-xl flex flex-wrap items-center justify-between gap-3">
                <span>Something went wrong. Retry.</span>
                <button
                    type="button"
                    onClick={() => setReloadKey((v) => v + 1)}
                    className="px-3 py-1.5 rounded-lg border border-rose-700 text-xs hover:bg-rose-900/30"
                >
                    Retry
                </button>
            </div>
        );
    }

    const scores = data?.scores || {};
    const optionSuggestions = data?.options_engine?.suggestions || [];

    return (
        <div className="p-4 lg:p-6 space-y-4">
            <RegimeCard
                regime={data?.overall_regime}
                confidence={data?.confidence}
                asOf={data?.as_of}
            />

            {error && (
                <div className="text-xs text-rose-200 bg-rose-900/30 border border-rose-800 rounded-xl px-3 py-2 flex flex-wrap items-center justify-between gap-2">
                    <span>Something went wrong. Retry.</span>
                    <button
                        type="button"
                        onClick={() => setReloadKey((v) => v + 1)}
                        className="px-2 py-1 rounded-md border border-rose-700 text-[11px] hover:bg-rose-900/30"
                    >
                        Retry
                    </button>
                </div>
            )}

            {loading && data && (
                <div className="text-xs text-slate-400">Loading...</div>
            )}

            <section className="grid md:grid-cols-2 xl:grid-cols-4 gap-3">
                <ScoreCard title="Growth Strength" score={scores.growth ?? 0} />
                <ScoreCard title="Inflation Pressure" score={scores.inflation ?? 0} />
                <ScoreCard title="Liquidity Strength" score={scores.liquidity ?? 0} />
                <ScoreCard title="Risk Appetite Strength" score={scores.risk_appetite ?? 0} />
            </section>

            <SignalTable signals={data?.signals || []} />

            <section className="grid lg:grid-cols-2 gap-4">
                <NarrativePanel narrative={data?.narrative} />
                <PlaybookPanel playbook={data?.playbook || {}} />
            </section>

            <OptionsEnginePanel
                riskTolerance={riskTolerance}
                positionContext={positionContext}
                ivContext={ivContext}
                onRiskToleranceChange={setRiskTolerance}
                onPositionContextChange={setPositionContext}
                onIvContextChange={setIvContext}
                suggestions={optionSuggestions}
                disabled={loading}
            />

            <section className="bg-slate-900/30 border border-slate-800 rounded-xl px-4 py-3">
                <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                    How to read this dashboard
                </h2>
                <ul className="mt-2 space-y-1 text-xs text-slate-400 leading-relaxed">
                    <li>Market Direction tells you if conditions favor risk-taking or caution.</li>
                    <li>Strength values summarize broad market pressure from -100 to +100.</li>
                    <li>Use Recommendations and Playbook as your next-action checklist.</li>
                </ul>
            </section>
        </div>
    );
}
