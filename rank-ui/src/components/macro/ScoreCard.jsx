function toneClass(score) {
    if (score >= 25) return "text-emerald-300 border-emerald-700/60";
    if (score <= -25) return "text-rose-300 border-rose-700/60";
    return "text-slate-200 border-slate-700";
}

function barColor(score) {
    if (score >= 25) return "bg-emerald-500";
    if (score <= -25) return "bg-rose-500";
    return "bg-slate-400";
}

export default function ScoreCard({ title, score }) {
    const value = typeof score === "number" ? score : 0;
    const clamped = Math.max(-100, Math.min(100, value));
    const width = Math.abs(clamped);

    return (
        <div className={`rounded-2xl border bg-slate-900/50 p-4 ${toneClass(value)}`}>
            <div className="text-xs uppercase tracking-wide text-slate-400">{title}</div>
            <div className="text-2xl font-semibold mt-1">{value.toFixed(1)}</div>
            <div className="mt-3 h-2 w-full rounded-full bg-slate-800 overflow-hidden">
                <div
                    className={`h-full ${barColor(value)}`}
                    style={{ width: `${width}%` }}
                    aria-hidden="true"
                />
            </div>
            <div className="mt-1 text-[11px] text-slate-500">Range: -100 to +100</div>
        </div>
    );
}
