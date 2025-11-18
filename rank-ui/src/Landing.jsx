// ==============================
// File: src/Landing.jsx
// Logged-out landing page + embedded Login form
// ==============================

import Login from "./Login.jsx";
import { APP_NAME, APP_TAGLINE } from "./brand";

export default function Landing() {
    return (
        <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
            {/* Top mini-nav */}
            <header className="border-b border-slate-800 bg-slate-950/80 backdrop-blur">
                <div className="max-w-6xl mx-auto px-4 sm:px-6 py-3 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-xl bg-indigo-600 flex items-center justify-center text-xs font-bold">
                            SR
                        </div>
                        <div className="flex flex-col">
                            <span className="text-sm font-semibold tracking-wide">
                                {APP_NAME}
                            </span>
                            <span className="text-xs text-slate-400">{APP_TAGLINE}</span>
                        </div>
                    </div>

                    <div className="hidden sm:flex items-center gap-3 text-xs text-slate-400">
                        <span>Already have an account?</span>
                        <span className="px-3 py-1.5 rounded-full border border-slate-700">
                            Sign in below
                        </span>
                    </div>
                </div>
            </header>

            {/* Hero */}
            <main className="flex-1">
                <div className="max-w-6xl mx-auto px-4 sm:px-6 py-10 grid gap-8 lg:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)] items-center">
                    {/* Left: marketing copy */}
                    <section className="space-y-5">
                        <div className="inline-flex items-center gap-2 text-xs px-3 py-1 rounded-full bg-emerald-900/20 border border-emerald-700/60 text-emerald-200">
                            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                            <span>Private beta • Internal use only</span>
                        </div>

                        <h1 className="text-3xl sm:text-4xl lg:text-5xl font-bold leading-tight">
                            Rank stocks by{" "}
                            <span className="text-indigo-400">signals and fundamentals</span>{" "}
                            in one click.
                        </h1>

                        <p className="text-sm sm:text-base text-slate-300 max-w-xl">
                            {APP_NAME} turns noisy charts and financials into a single,
                            tunable score. Run baskets, save watchlists, set email alerts, and
                            backtest simple Top-N strategies against SPY.
                        </p>

                        <ul className="space-y-2 text-sm text-slate-300">
                            <li className="flex gap-2">
                                <span className="mt-1 text-emerald-400">▸</span>
                                <span>
                                    Combine trend, momentum, volume, volatility, and mean
                                    reversion with sliders — no code required.
                                </span>
                            </li>
                            <li className="flex gap-2">
                                <span className="mt-1 text-emerald-400">▸</span>
                                <span>
                                    Save ranked baskets as watchlists and get{" "}
                                    <strong>email alerts</strong> when scores cross your
                                    thresholds.
                                </span>
                            </li>
                            <li className="flex gap-2">
                                <span className="mt-1 text-emerald-400">▸</span>
                                <span>
                                    Run quick Top-N backtests vs SPY to see if your settings have
                                    any edge.
                                </span>
                            </li>
                        </ul>

                        <div className="flex flex-wrap gap-3 text-xs text-slate-400 pt-2">
                            <span className="px-2 py-1 rounded-full border border-slate-700">
                                Built for personal research
                            </span>
                            <span className="px-2 py-1 rounded-full border border-slate-700">
                                Not investment advice
                            </span>
                        </div>
                    </section>

                    {/* Right: login card */}
                    <section className="bg-slate-950 border border-slate-800 rounded-2xl p-4 sm:p-5 shadow-xl shadow-indigo-900/20">
                        <div className="mb-3 text-center">
                            <h2 className="text-base sm:text-lg font-semibold">
                                Sign in to your dashboard
                            </h2>
                            <p className="text-xs text-slate-400 mt-1">
                                Use the same credentials you created for the API. Everything is
                                scoped to your account.
                            </p>
                        </div>

                        {/* We just reuse your existing Login component here */}
                        <Login />
                    </section>
                </div>
            </main>

            <footer className="border-t border-slate-900 text-xs text-slate-500 py-3 px-4">
                <div className="max-w-6xl mx-auto flex justify-between items-center gap-3">
                    <span>© {new Date().getFullYear()} {APP_NAME}</span>
                    <span className="hidden sm:inline">
                        For educational use only • No guarantees • Markets are risky.
                    </span>
                </div>
            </footer>
        </div>
    );
}
