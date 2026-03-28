export default function PlaybookPanel({ playbook = {} }) {
    const favored = Array.isArray(playbook.favored_assets) ? playbook.favored_assets : [];
    const unfavorable = Array.isArray(playbook.unfavorable_assets) ? playbook.unfavorable_assets : [];

    return (
        <section className="bg-slate-900/50 border border-slate-800 rounded-2xl p-4">
            <h2 className="text-sm font-semibold text-slate-200">What should I do</h2>
            <div className="mt-3 grid sm:grid-cols-2 gap-4 text-sm">
                <div>
                    <div className="text-xs uppercase tracking-wide text-emerald-300">Lean toward</div>
                    <ul className="mt-1 space-y-1 text-slate-300">
                        {favored.map((item) => (
                            <li key={item}>- {item}</li>
                        ))}
                        {!favored.length && <li className="text-slate-500">- None</li>}
                    </ul>
                </div>
                <div>
                    <div className="text-xs uppercase tracking-wide text-rose-300">Use caution with</div>
                    <ul className="mt-1 space-y-1 text-slate-300">
                        {unfavorable.map((item) => (
                            <li key={item}>- {item}</li>
                        ))}
                        {!unfavorable.length && <li className="text-slate-500">- None</li>}
                    </ul>
                </div>
            </div>
            <p className="mt-3 text-sm text-slate-400">{playbook.notes || "No extra notes right now."}</p>
        </section>
    );
}
