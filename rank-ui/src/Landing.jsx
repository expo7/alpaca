import Login from "./Login.jsx";
import { APP_NAME } from "./brand";
import SiteFooter from "./components/SiteFooter.jsx";

const workflow = [
    { number: "01", title: "Qualify a setup", copy: "Research produces a specific options plan only when the contract and entry conditions qualify." },
    { number: "02", title: "Publish the plan", copy: "The contract, trigger, stop, targets, risk, and evidence are recorded before entry. Active details may require Pro access." },
    { number: "03", title: "Monitor the paper trade", copy: "The Alpaca paper executor follows a qualifying entry and its protective exit. Material lifecycle events reach the Telegram alert channel." },
    { number: "04", title: "Keep every result", copy: "The public record retains completed paper outcomes, losses, cancellations, expirations, and setups that never filled." },
];

export default function Landing() {
    return (
        <div className="min-h-screen bg-slate-950 text-slate-100">
            <header className="border-b border-slate-800/80 bg-slate-950/90">
                <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4 sm:px-6">
                    <a href="/" className="flex min-w-0 flex-col">
                        <span className="truncate text-[0.78rem] font-black tracking-[0.14em] text-white">
                            {APP_NAME.toUpperCase()}
                        </span>
                        <span className="hidden text-xs text-slate-500 sm:block">Options research with a public trade record</span>
                    </a>
                    <nav aria-label="Main navigation" className="flex items-center gap-3 text-sm">
                        <a href="/signals" className="text-slate-300 hover:text-white">Live Options</a>
                        <a href="/articles" className="hidden text-slate-300 hover:text-white sm:inline">Articles</a>
                        <a href="#sign-in" className="rounded-full border border-slate-700 px-3 py-1.5 text-slate-200 hover:bg-slate-900">Sign in</a>
                    </nav>
                </div>
            </header>

            <main>
                <section className="relative overflow-hidden border-b border-slate-800/70">
                    <div className="absolute inset-0 bg-[radial-gradient(circle_at_75%_20%,rgba(79,70,229,0.18),transparent_35%)]" />
                    <div className="relative mx-auto grid max-w-6xl gap-10 px-4 py-14 sm:px-6 sm:py-20 lg:grid-cols-[1.1fr_0.9fr] lg:items-center">
                        <div>
                            <div className="inline-flex rounded-full border border-emerald-800/70 bg-emerald-950/30 px-3 py-1 text-xs font-medium text-emerald-300">
                                Options research · Public trade record
                            </div>
                            <h1 className="mt-5 max-w-3xl text-4xl font-bold leading-[1.08] tracking-tight sm:text-5xl lg:text-6xl">
                                Trade ideas with a plan.<br /><span className="text-indigo-300">Outcomes you can check.</span>
                            </h1>
                            <p className="mt-5 max-w-2xl text-base leading-7 text-slate-300 sm:text-lg">
                                Quantelle publishes options plans with entry conditions, risk levels, stops, and targets. Explore the public record of pending, open, and completed paper setups; active details may require Pro access.
                            </p>
                            <div className="mt-7 flex flex-wrap gap-3">
                                <a href="/signals" className="rounded-xl bg-indigo-600 px-5 py-3 font-semibold text-white shadow-lg shadow-indigo-950/40 hover:bg-indigo-500">
                                    Explore Live Options
                                </a>
                                <a href="https://t.me/+6zJGLH-XJWY0MTcx" target="_blank" rel="noreferrer" className="rounded-xl border border-sky-700 bg-sky-950/40 px-5 py-3 font-semibold text-sky-200 hover:bg-sky-950/70">
                                    Quantelle Trade Alerts
                                </a>
                            </div>
                            <p className="mt-4 text-xs text-slate-500">Free public record · Alpaca paper execution and returns · No brokerage connection required to browse</p>
                        </div>

                        <div className="rounded-3xl border border-slate-700/80 bg-slate-900/75 p-5 shadow-2xl shadow-indigo-950/30 backdrop-blur">
                            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
                                <div>
                                    <div className="text-xs font-semibold uppercase tracking-[0.16em] text-indigo-300">Inside a Quantelle setup</div>
                                    <div className="mt-1 text-lg font-semibold">A plan before an entry</div>
                                </div>
                                <span className="rounded-full border border-sky-800 bg-sky-950/40 px-3 py-1 text-xs font-semibold text-sky-300">PAPER TRADE</span>
                            </div>
                            <div className="mt-4 grid gap-3 sm:grid-cols-2">
                                <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-4">
                                    <div className="text-xs uppercase tracking-wide text-slate-500">Before entry</div>
                                    <div className="mt-2 font-medium">Contract, trigger, and do-not-chase level</div>
                                </div>
                                <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-4">
                                    <div className="text-xs uppercase tracking-wide text-slate-500">Defined risk</div>
                                    <div className="mt-2 font-medium">Stop, targets, and invalidation</div>
                                </div>
                            </div>
                            <div className="mt-3 rounded-xl border border-indigo-800/60 bg-indigo-950/25 p-4 text-sm leading-6 text-slate-300">
                                Trade cards show the <span className="font-semibold text-white">current state and latest update</span>. Completed setups show the realized paper result, including losses; unfilled ideas remain visible.
                            </div>
                        </div>
                    </div>
                </section>

                <section id="how-it-works" className="mx-auto max-w-6xl scroll-mt-8 px-4 py-14 sm:px-6">
                    <div className="max-w-2xl">
                        <div className="text-xs font-semibold uppercase tracking-[0.16em] text-indigo-300">How Quantelle works</div>
                        <h2 className="mt-2 text-3xl font-bold tracking-tight">From setup to outcome</h2>
                        <p className="mt-3 leading-7 text-slate-400">A candidate becomes a published trade only when its conditions qualify. If an entry never triggers, that remains part of the record too.</p>
                    </div>
                    <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                        {workflow.map((item) => (
                            <article key={item.number} className="rounded-2xl border border-slate-800 bg-slate-900/45 p-5">
                                <div className="font-mono text-sm text-indigo-400">{item.number}</div>
                                <h3 className="mt-4 text-lg font-semibold">{item.title}</h3>
                                <p className="mt-2 text-sm leading-6 text-slate-400">{item.copy}</p>
                            </article>
                        ))}
                    </div>
                </section>

                <section className="border-t border-slate-800/70 bg-slate-900/35">
                    <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-12 sm:px-6 md:flex-row md:items-center md:justify-between">
                        <div className="max-w-2xl">
                            <h2 className="text-2xl font-bold">See the complete record, including the misses.</h2>
                            <p className="mt-2 leading-7 text-slate-400">Active positions, waiting entries, and completed filled trades have separate views. Cancelled, expired, and unfilled setups remain in their own history. Completed paper trades show their realized results.</p>
                        </div>
                        <a href="/signals" className="self-start whitespace-nowrap rounded-xl border border-indigo-500/60 px-5 py-3 font-semibold text-indigo-200 hover:bg-indigo-950/50">View trade history</a>
                    </div>
                </section>

                <section id="sign-in" className="border-t border-slate-800/70 bg-slate-900/25">
                    <div className="mx-auto grid max-w-5xl gap-8 px-4 py-14 sm:px-6 lg:grid-cols-[0.9fr_1.1fr] lg:items-center">
                        <div>
                            <div className="text-xs font-semibold uppercase tracking-[0.16em] text-emerald-300">Keep your research together</div>
                            <h2 className="mt-2 text-3xl font-bold">Save the names worth watching.</h2>
                            <p className="mt-3 leading-7 text-slate-400">The trade record and market context are public. Create a free account to build a watchlist and follow the ratings that matter to you.</p>
                        </div>
                        <div className="lg:justify-self-end lg:w-full lg:max-w-md">
                            <Login />
                        </div>
                    </div>
                </section>
            </main>

            <SiteFooter />
        </div>
    );
}
