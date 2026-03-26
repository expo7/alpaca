import { useEffect, useState } from "react";
import { useAuth } from "../AuthProvider.jsx";
import { getMacroDashboard } from "../api/macro.js";
import RegimeCard from "../components/macro/RegimeCard.jsx";
import ScoreCard from "../components/macro/ScoreCard.jsx";
import SignalTable from "../components/macro/SignalTable.jsx";
import NarrativePanel from "../components/macro/NarrativePanel.jsx";
import PlaybookPanel from "../components/macro/PlaybookPanel.jsx";
import OptionsEnginePanel from "../components/macro/OptionsEnginePanel.jsx";

export default function MacroDashboardPage() {
    const { token } = useAuth();
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [data, setData] = useState(null);
    const [riskTolerance, setRiskTolerance] = useState("moderate");
    const [positionContext, setPositionContext] = useState("flat");
    const [ivContext, setIvContext] = useState("normal");

    useEffect(() => {
        if (!token) return;
        let cancelled = false;

        (async () => {
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
                if (!cancelled) setLoading(false);
            }
        })();

        return () => {
            cancelled = true;
        };
    }, [token, riskTolerance, positionContext, ivContext]);

    if (!token) {
        return (
            <div className="p-4 text-sm text-amber-300">
                Login required to view the macro dashboard.
            </div>
        );
    }

    if (loading && !data) {
        return <div className="p-4 text-sm text-slate-400">Loading macro dashboard...</div>;
    }

    if (error && !data) {
        return (
            <div className="p-4 text-sm text-rose-300 bg-rose-900/30 border border-rose-800 rounded-xl">
                {error}
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
                <div className="text-xs text-rose-200 bg-rose-900/30 border border-rose-800 rounded-xl px-3 py-2">
                    {error}
                </div>
            )}

            <section className="grid md:grid-cols-2 xl:grid-cols-4 gap-3">
                <ScoreCard title="Growth Score" score={scores.growth ?? 0} />
                <ScoreCard title="Inflation Score" score={scores.inflation ?? 0} />
                <ScoreCard title="Liquidity Score" score={scores.liquidity ?? 0} />
                <ScoreCard title="Risk Appetite Score" score={scores.risk_appetite ?? 0} />
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
            />

            <section className="bg-slate-900/30 border border-slate-800 rounded-xl px-4 py-3">
                <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                    How to read this dashboard
                </h2>
                <ul className="mt-2 space-y-1 text-xs text-slate-400 leading-relaxed">
                    <li>Scores are proxy-based cross-asset signals, designed to summarize broad macro tone.</li>
                    <li>Confidence reflects internal signal consistency, not a forecast probability.</li>
                    <li>Regime labels are intentionally coarse and may compress transition periods.</li>
                </ul>
            </section>
        </div>
    );
}
