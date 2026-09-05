import Login from "./Login.jsx";
import { APP_NAME } from "./brand";

const workflow = [
    { number: "01", title: "Read the market", copy: "See whether conditions favor offense, defense, or patience." },
    { number: "02", title: "Focus on five", copy: "Start with a short list of ranked research ideas instead of an endless feed." },
    { number: "03", title: "Verify the setup", copy: "Open the evidence behind each rating before deciding whether it belongs in your plan." },
];

export default function Landing() {
    return (
        <div className="min-h-screen bg-slate-950 text-slate-100">
            <header className="border-b border-slate-800/80 bg-slate-950/90">
                <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4 sm:px-6">
                    <a href="/" className="flex items-center gap-3">
                        <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-600 text-sm font-bold">Q</span>
                        <span>
                            <span className="block font-semibold tracking-wide">{APP_NAME}</span>
                            <span className="block text-xs text-slate-500">Daily market decisions</span>
                        </span>
                    </a>
                    <nav className="flex items-center gap-3 text-sm">
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
                                Market context + ranked opportunities
                            </div>
                            <h1 className="mt-5 max-w-3xl text-4xl font-bold leading-[1.08] tracking-tight sm:text-5xl lg:text-6xl">
                                Five focused ideas.<br />One plan for today.
                            </h1>
                            <p className="mt-5 max-w-2xl text-base leading-7 text-slate-300 sm:text-lg">
                                Quantelle turns market conditions, technical strength, and fundamentals into a short daily research list—so you know where to look and when to stay cautious.
                            </p>
                            <div className="mt-7 flex flex-wrap gap-3">
                                <a href="/dashboard" className="rounded-xl bg-indigo-600 px-5 py-3 font-semibold text-white shadow-lg shadow-indigo-950/40 hover:bg-indigo-500">
                                    See today&apos;s plan
                                </a>
                                <a href="/opportunities" className="rounded-xl border border-slate-700 bg-slate-900/60 px-5 py-3 font-semibold text-slate-200 hover:bg-slate-900">
                                    Explore opportunities
                                </a>
                            </div>
                            <p className="mt-4 text-xs text-slate-500">Free research preview · No brokerage connection required · Not investment advice</p>
                        </div>

                        <div className="rounded-3xl border border-slate-700/80 bg-slate-900/75 p-5 shadow-2xl shadow-indigo-950/30 backdrop-blur">
                            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
                                <div>
                                    <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Today&apos;s research brief</div>
                                    <div className="mt-1 text-lg font-semibold">A decision before a ticker</div>
                                </div>
                                <span className="rounded-full border border-amber-700/70 bg-amber-950/40 px-3 py-1 text-xs font-semibold text-amber-300">SELECTIVE</span>
                            </div>
                            <div className="mt-4 grid gap-3 sm:grid-cols-2">
                                <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-4">
                                    <div className="text-xs uppercase tracking-wide text-slate-500">Market first</div>
                                    <div className="mt-2 font-medium">Set exposure before choosing ideas</div>
                                </div>
                                <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-4">
                                    <div className="text-xs uppercase tracking-wide text-slate-500">Then focus</div>
                                    <div className="mt-2 font-medium">Review five ranked opportunities</div>
                                </div>
                            </div>
                            <div className="mt-3 rounded-xl border border-indigo-800/60 bg-indigo-950/25 p-4 text-sm leading-6 text-slate-300">
                                Every rating should answer two questions: <span className="font-semibold text-white">why this idea</span> and <span className="font-semibold text-white">why now</span>.
                            </div>
                        </div>
                    </div>
                </section>

                <section className="mx-auto max-w-6xl px-4 py-14 sm:px-6">
                    <div className="max-w-2xl">
                        <div className="text-xs font-semibold uppercase tracking-[0.16em] text-indigo-300">A tighter daily workflow</div>
                        <h2 className="mt-2 text-3xl font-bold tracking-tight">Less dashboard. More decision.</h2>
                    </div>
                    <div className="mt-8 grid gap-4 md:grid-cols-3">
                        {workflow.map((item) => (
                            <article key={item.number} className="rounded-2xl border border-slate-800 bg-slate-900/45 p-5">
                                <div className="font-mono text-sm text-indigo-400">{item.number}</div>
                                <h3 className="mt-4 text-lg font-semibold">{item.title}</h3>
                                <p className="mt-2 text-sm leading-6 text-slate-400">{item.copy}</p>
                            </article>
                        ))}
                    </div>
                </section>

                <section id="sign-in" className="border-t border-slate-800/70 bg-slate-900/25">
                    <div className="mx-auto grid max-w-5xl gap-8 px-4 py-14 sm:px-6 lg:grid-cols-[0.9fr_1.1fr] lg:items-center">
                        <div>
                            <div className="text-xs font-semibold uppercase tracking-[0.16em] text-emerald-300">Keep your research together</div>
                            <h2 className="mt-2 text-3xl font-bold">Save the names worth watching.</h2>
                            <p className="mt-3 leading-7 text-slate-400">The market plan and opportunities are public. Create a free account to build a watchlist and follow the ratings that matter to you.</p>
                        </div>
                        <div className="rounded-2xl border border-slate-800 bg-slate-950 p-5 shadow-xl">
                            <Login />
                        </div>
                    </div>
                </section>
            </main>

            <footer className="border-t border-slate-900 px-4 py-5 text-xs text-slate-500">
                <div className="mx-auto flex max-w-6xl flex-wrap justify-between gap-2">
                    <span>© {new Date().getFullYear()} {APP_NAME}</span>
                    <span>Research only · No guarantees · Markets involve risk</span>
                </div>
            </footer>
        </div>
    );
}
