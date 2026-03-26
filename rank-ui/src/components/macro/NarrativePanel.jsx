export default function NarrativePanel({ narrative }) {
    return (
        <section className="bg-slate-900/50 border border-slate-800 rounded-2xl p-4">
            <h2 className="text-sm font-semibold text-slate-200">Narrative</h2>
            <p className="mt-2 text-sm text-slate-300 leading-relaxed">
                {narrative || "Narrative unavailable."}
            </p>
        </section>
    );
}
