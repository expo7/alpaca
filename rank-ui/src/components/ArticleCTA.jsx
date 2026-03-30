export default function ArticleCTA({ isAuthed, onViewDashboard, onSignUp }) {
    return (
        <section className="border-t border-slate-700 mt-12 pt-12">
            <div className="max-w-3xl mx-auto px-4 sm:px-6">
                <div className="bg-gradient-to-br from-slate-900/80 to-slate-950 border border-slate-700 rounded-lg p-8 space-y-6">
                    <div className="space-y-2">
                        <h2 className="text-xl sm:text-2xl font-bold">See today's market view in Quantelle</h2>
                        <p className="text-sm text-slate-300">
                            Quantelle turns market conditions into a simple daily recommendation, ranked opportunities, and a watchlist you can revisit daily.
                        </p>
                    </div>

                    <div className="flex flex-col sm:flex-row gap-3">
                        {isAuthed ? (
                            <button
                                type="button"
                                onClick={onViewDashboard}
                                className="px-4 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-sm transition"
                            >
                                View Dashboard
                            </button>
                        ) : (
                            <>
                                <button
                                    type="button"
                                    onClick={onViewDashboard}
                                    className="px-4 py-2.5 rounded-lg border border-slate-600 hover:bg-slate-900 text-slate-200 font-medium text-sm transition"
                                >
                                    View Dashboard
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
                        Published by Quantelle, a daily market decision engine.
                    </p>
                </div>
            </div>
        </section>
    );
}
