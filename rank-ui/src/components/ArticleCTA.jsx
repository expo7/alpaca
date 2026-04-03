export default function ArticleCTA({ isAuthed, onViewDashboard, onSignUp }) {
    return (
        <section className="border-t border-slate-700 mt-12 pt-12">
            <div className="max-w-3xl mx-auto px-4 sm:px-6">
                <div className="bg-gradient-to-br from-slate-900/80 to-slate-950 border border-slate-700 rounded-lg p-8 space-y-6">
                    <div className="space-y-2">
                        <h2 className="text-xl sm:text-2xl font-bold">
                            See how Quantelle reads today’s market conditions
                        </h2>
                        <p className="text-sm text-slate-300">
                            Quantelle helps turn market context into a daily view you can actually use before looking at individual stocks.
                        </p>
                    </div>

                    <div className="grid gap-2 text-sm text-slate-200">
                        <p>• Current market regime: risk-on, risk-off, or neutral</p>
                        <p>• Ranked opportunities based on the current environment</p>
                        <p>• A watchlist you can revisit as conditions change</p>
                        <p>• Free account — no credit card or email required</p>
                    </div>

                    <div className="flex flex-col sm:flex-row gap-3">
                        {isAuthed ? (
                            <button
                                type="button"
                                onClick={onViewDashboard}
                                className="px-4 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-sm transition"
                            >
                                View Today’s Dashboard
                            </button>
                        ) : (
                            <>
                                <button
                                    type="button"
                                    onClick={onViewDashboard}
                                    className="px-4 py-2.5 rounded-lg border border-slate-600 hover:bg-slate-900 text-slate-200 font-medium text-sm transition"
                                >
                                    Preview Dashboard
                                </button>
                                <button
                                    type="button"
                                    onClick={onSignUp}
                                    className="px-4 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-sm transition"
                                >
                                    Create Free Account
                                </button>
                            </>
                        )}
                    </div>

                    <p className="text-xs text-slate-500">
                        Built to help you see when the environment supports a setup — and when it probably doesn’t.
                    </p>
                </div>
            </div>
        </section>
    );
}
