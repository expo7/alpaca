function fmt(v) {
    if (typeof v !== "number") return "-";
    return v.toFixed(2);
}

export default function SignalTable({ signals = [] }) {
    return (
        <section className="bg-slate-900/50 border border-slate-800 rounded-2xl overflow-hidden">
            <div className="px-4 py-3 border-b border-slate-800">
                <h2 className="text-sm font-semibold text-slate-200">Cross-Asset Recommendations</h2>
                <p className="mt-1 text-xs text-slate-400">Read what is moving, then follow the recommendation.</p>
            </div>
            <div className="overflow-auto">
                <table className="w-full text-xs sm:text-sm">
                    <thead className="text-slate-400 bg-slate-900/60">
                        <tr>
                            <th className="px-3 py-2 text-left">Symbol</th>
                            <th className="px-3 py-2 text-left">Name</th>
                            <th className="px-3 py-2 text-right">Price</th>
                            <th className="px-3 py-2 text-right">5D %</th>
                            <th className="px-3 py-2 text-right">20D %</th>
                            <th className="px-3 py-2 text-right">60D %</th>
                            <th className="px-3 py-2 text-right">Dist 50DMA %</th>
                            <th className="px-3 py-2 text-left">Recommendation</th>
                            <th className="px-3 py-2 text-left">Interpretation</th>
                        </tr>
                    </thead>
                    <tbody>
                        {signals.map((row) => (
                            <tr key={`${row.symbol}-${row.name}`} className="border-t border-slate-800 align-top">
                                <td className="px-3 py-2 font-semibold text-slate-100">{row.symbol}</td>
                                <td className="px-3 py-2 text-slate-300">{row.name}</td>
                                <td className="px-3 py-2 text-right">{fmt(row.price)}</td>
                                <td className="px-3 py-2 text-right">{fmt(row.ret_5d)}</td>
                                <td className="px-3 py-2 text-right">{fmt(row.ret_20d)}</td>
                                <td className="px-3 py-2 text-right">{fmt(row.ret_60d)}</td>
                                <td className="px-3 py-2 text-right">{fmt(row.dist_50dma)}</td>
                                <td className="px-3 py-2 text-slate-100">{row.signal}</td>
                                <td className="px-3 py-2 text-slate-400 min-w-[240px]">{row.interpretation}</td>
                            </tr>
                        ))}
                        {!signals.length && (
                            <tr>
                                <td className="px-3 py-4 text-center text-slate-500" colSpan={9}>
                                    No recommendations available.
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>
        </section>
    );
}
