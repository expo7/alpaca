export default function RegimeCard({ regime, confidence, asOf }) {
    const label = regime || "Unavailable";
    const lower = String(label).toLowerCase();

    let hint = "mixed conditions; keep position sizes moderate";
    if (lower.includes("risk-off")) {
        hint = "higher risk of downside; stay defensive";
    } else if (lower.includes("risk-on")) {
        hint = "buyers are in control; favor quality longs";
    }

    return (
        <section className="bg-slate-900/50 border border-slate-800 rounded-2xl p-4 lg:p-5">
            <div className="text-xs text-slate-400 uppercase tracking-wide">Market Direction</div>
            <div className="mt-2 text-2xl font-semibold text-slate-100">{label}</div>
            <p className="mt-2 text-xs text-slate-300">{hint}</p>
            <div className="mt-3 flex flex-wrap gap-3 text-sm text-slate-300">
                <span className="px-2 py-1 rounded-full bg-slate-800 border border-slate-700">
                    Confidence: {typeof confidence === "number" ? `${confidence}%` : "N/A"}
                </span>
                <span className="px-2 py-1 rounded-full bg-slate-800 border border-slate-700">
                    As of: {asOf || "N/A"}
                </span>
            </div>
        </section>
    );
}
