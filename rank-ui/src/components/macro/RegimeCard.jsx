export default function RegimeCard({ regime, confidence, asOf }) {
    return (
        <section className="bg-slate-900/50 border border-slate-800 rounded-2xl p-4 lg:p-5">
            <div className="text-xs text-slate-400 uppercase tracking-wide">Macro Regime</div>
            <div className="mt-2 text-2xl font-semibold text-slate-100">{regime || "Unavailable"}</div>
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
