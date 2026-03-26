function SetupRow({ setup = {} }) {
    return (
        <div className="grid sm:grid-cols-3 gap-2 text-xs text-slate-400 mt-2">
            <div className="min-w-0 break-words">
                <span className="text-slate-500">DTE:</span> {setup.dte || "-"}
            </div>
            <div className="min-w-0 break-words">
                <span className="text-slate-500">Delta:</span> {setup.delta_target || "-"}
            </div>
            <div className="min-w-0 break-words">
                <span className="text-slate-500">Bias:</span> {setup.bias || "-"}
            </div>
        </div>
    );
}

function ListLine({ title, items = [] }) {
    return (
        <div className="text-xs mt-2">
            <div className="text-slate-500 uppercase tracking-wide">{title}</div>
            <div className="text-slate-400 mt-1">{items.length ? items.join(" • ") : "-"}</div>
        </div>
    );
}

export default function OptionsEnginePanel({
    riskTolerance,
    positionContext,
    ivContext,
    onRiskToleranceChange,
    onPositionContextChange,
    onIvContextChange,
    suggestions = [],
}) {
    return (
        <section className="bg-slate-900/50 border border-slate-800 rounded-2xl p-4 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                    <h2 className="text-sm font-semibold text-slate-200">Options Engine</h2>
                    <p className="text-xs text-slate-400">
                        Rule-based structures based on macro regime, confidence, and your context.
                    </p>
                </div>

                <div className="grid sm:grid-cols-3 gap-2 w-full lg:w-auto">
                    <select
                        value={riskTolerance}
                        onChange={(e) => onRiskToleranceChange(e.target.value)}
                        className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5 text-xs"
                    >
                        <option value="conservative">Risk: Conservative</option>
                        <option value="moderate">Risk: Moderate</option>
                        <option value="aggressive">Risk: Aggressive</option>
                    </select>

                    <select
                        value={positionContext}
                        onChange={(e) => onPositionContextChange(e.target.value)}
                        className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5 text-xs"
                    >
                        <option value="flat">Position: Flat</option>
                        <option value="long_shares">Position: Long Shares</option>
                    </select>

                    <select
                        value={ivContext}
                        onChange={(e) => onIvContextChange(e.target.value)}
                        className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5 text-xs"
                    >
                        <option value="low">IV: Low</option>
                        <option value="normal">IV: Normal</option>
                        <option value="high">IV: High</option>
                    </select>
                </div>
            </div>

            <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3">
                {suggestions.slice(0, 3).map((row) => (
                    <article
                        key={row.strategy}
                        className="bg-slate-950/60 border border-slate-800 rounded-xl p-3"
                    >
                        <div className="flex items-center justify-between gap-2">
                            <div className="text-sm font-semibold text-slate-100">{row.label}</div>
                            <span className="text-[11px] px-2 py-0.5 rounded-full border border-slate-700 text-slate-400">
                                Priority {row.priority}
                            </span>
                        </div>

                        <p className="text-xs text-slate-400 mt-2">{row.reason}</p>
                        <SetupRow setup={row.setup} />
                        <ListLine title="Fits When" items={row.fits_when} />
                        <ListLine title="Avoid When" items={row.avoid_when} />
                    </article>
                ))}

                {!suggestions.length && (
                    <div className="text-xs text-slate-500 border border-dashed border-slate-700 rounded-xl p-3">
                        No option suggestions available for the current context.
                    </div>
                )}
            </div>
        </section>
    );
}
