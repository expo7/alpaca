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
                            Q
                        </div>
                        <div className="flex flex-col">
                            <span className="text-sm font-semibold tracking-wide">
                                {APP_NAME}
                            </span>
                            <span className="text-xs text-slate-400">{APP_TAGLINE}</span>
                        </div>
                    </div>

                    <div className="hidden sm:flex items-center gap-3 text-xs text-slate-400">
                        <a href="/articles" className="text-slate-300 hover:text-white">
                            Articles
                        </a>
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
                            Make better trading decisions in seconds
                        </h1>

                        <p className="text-sm sm:text-base text-slate-300 max-w-xl">
                            Quantelle analyzes the market and tells you what to do today-so you don't have to guess.
                        </p>

                        <ul className="space-y-3 text-sm text-slate-300">
                            <li className="flex gap-2">
                                <span className="mt-1 text-emerald-400">▸</span>
                                <span>
                                    <span className="font-semibold text-slate-100">See today's market outlook.</span>{" "}
                                    Understand if conditions are favorable or risky.
                                </span>
                            </li>
                            <li className="flex gap-2">
                                <span className="mt-1 text-emerald-400">▸</span>
                                <span>
                                    <span className="font-semibold text-slate-100">Know what to do.</span>{" "}
                                    Get a clear daily recommendation-no noise, no overthinking.
                                </span>
                            </li>
                            <li className="flex gap-2">
                                <span className="mt-1 text-emerald-400">▸</span>
                                <span>
                                    <span className="font-semibold text-slate-100">Focus on the right stocks.</span>{" "}
                                    View top-ranked opportunities based on real signals.
                                </span>
                            </li>
                            <li className="flex gap-2">
                                <span className="mt-1 text-emerald-400">▸</span>
                                <span>
                                    <span className="font-semibold text-slate-100">Track what matters to you.</span>{" "}
                                    Save tickers to your watchlist and check them daily.
                                </span>
                            </li>
                        </ul>

                        <div className="pt-1">
                            <a
                                href="#auth-card"
                                className="inline-flex items-center justify-center rounded-xl bg-indigo-600 hover:bg-indigo-500 px-4 py-2 text-sm font-semibold text-white"
                            >
                                Get today's recommendation
                            </a>
                        </div>

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
                    <section id="auth-card" className="bg-slate-950 border border-slate-800 rounded-2xl p-4 sm:p-5 shadow-xl shadow-indigo-900/20">
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
