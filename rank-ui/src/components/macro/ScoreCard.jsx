function band(score) {
    if (score >= 25) return "high";
    if (score <= -25) return "low";
    return "mid";
}

function sentimentTone(sentiment) {
    if (sentiment === "favorable") return "text-emerald-200 border-emerald-700/60 bg-emerald-950/20";
    if (sentiment === "unfavorable") return "text-rose-200 border-rose-700/60 bg-rose-950/20";
    return "text-amber-200 border-amber-700/60 bg-amber-950/20";
}

function sentimentDot(sentiment) {
    if (sentiment === "favorable") return "bg-emerald-400";
    if (sentiment === "unfavorable") return "bg-rose-400";
    return "bg-amber-400";
}

function sentimentBar(sentiment) {
    if (sentiment === "favorable") return "bg-emerald-400";
    if (sentiment === "unfavorable") return "bg-rose-400";
    return "bg-amber-400";
}

function interpretMetric(metric, score) {
    const level = band(score);

    switch (metric) {
        case "inflation":
            if (level === "high") return { label: "Inflation Pressure: High", sentiment: "unfavorable" };
            if (level === "low") return { label: "Inflation Pressure: Low", sentiment: "favorable" };
            return { label: "Inflation Pressure: Moderate", sentiment: "neutral" };
        case "liquidity":
            if (level === "high") return { label: "Liquidity: Strong", sentiment: "favorable" };
            if (level === "low") return { label: "Liquidity: Weak", sentiment: "unfavorable" };
            return { label: "Liquidity: Neutral", sentiment: "neutral" };
        case "volatility":
            if (level === "high") return { label: "Market Volatility: Elevated", sentiment: "unfavorable" };
            if (level === "low") return { label: "Market Volatility: Low", sentiment: "favorable" };
            return { label: "Market Volatility: Normal", sentiment: "neutral" };
        case "risk_appetite":
            if (level === "high") return { label: "Risk Appetite: Favorable", sentiment: "favorable" };
            if (level === "low") return { label: "Risk Appetite: Defensive", sentiment: "unfavorable" };
            return { label: "Risk Appetite: Balanced", sentiment: "neutral" };
        case "momentum":
        default:
            if (level === "high") return { label: "Market Momentum: Strong", sentiment: "favorable" };
            if (level === "low") return { label: "Market Momentum: Weak", sentiment: "unfavorable" };
            return { label: "Market Momentum: Neutral", sentiment: "neutral" };
    }
}

export default function ScoreCard({ metric, score }) {
    const value = typeof score === "number" ? score : 0;
    const interpreted = interpretMetric(metric, value);
    const clamped = Math.max(-100, Math.min(100, value));
    const width = Math.abs(clamped);

    return (
        <div className={`rounded-2xl border p-4 ${sentimentTone(interpreted.sentiment)}`}>
            <div className="flex items-center gap-2">
                <span className={`h-2.5 w-2.5 rounded-full ${sentimentDot(interpreted.sentiment)}`} aria-hidden="true" />
                <div className="text-sm font-semibold">{interpreted.label}</div>
            </div>
            <div className="mt-3 h-2 w-full rounded-full bg-slate-800/70 overflow-hidden" aria-hidden="true">
                <div
                    className={`h-full ${sentimentBar(interpreted.sentiment)}`}
                    style={{ width: `${width}%` }}
                />
            </div>
            <div className="mt-2 text-[11px] text-slate-400">({Math.round(value)}/100)</div>
        </div>
    );
}
