import { useEffect, useRef, useState } from "react";
import Login from "./Login.jsx";
import SiteFooter from "./components/SiteFooter.jsx";
import Navbar from "./components/Navbar.jsx";

const workflow = [
    { number: "01", title: "Evaluate the plan", copy: "See the specific contract, entry conditions, stop, targets, and reasoning before deciding whether the idea fits." },
    { number: "02", title: "Follow the updates", copy: "Track the published plan through its paper lifecycle. An entry that never qualifies stays in the record too." },
    { number: "03", title: "Learn from the outcome", copy: "Compare the original plan with the completed result, including losses. Understand what worked and what changed." },
];
const guides = [
    { slug: "how-to-read-a-paper-options-trade-record", title: "How to read a paper options trade", copy: "Understand entries, stops, and realized returns using a documented trade record." },
    { slug: "mu-options-trade-setup-entry-matters-more-than-the-story", title: "Why the entry matters", copy: "See how a compelling market story becomes a specific, conditional trade plan." },
    { slug: "nvidia-nvda-options-trade-relative-strength-breakout", title: "Follow the reasoning behind a setup", copy: "Explore a published NVIDIA idea and the evidence behind its entry conditions." },
];

export default function Landing() {
    const [signInOpen, setSignInOpen] = useState(false);
    const dialogRef = useRef(null);

    useEffect(() => {
        if (!signInOpen) return;
        const dialog = dialogRef.current;
        dialog.showModal();
        dialog.querySelector("input")?.focus();
        return () => { if (dialog.open) dialog.close(); };
    }, [signInOpen]);

    return (
        <div className="min-h-screen bg-slate-950 text-slate-100">
            <Navbar v1Mode onNavigate={(page) => { window.location.href = `/${page}`; }} onSignIn={() => setSignInOpen(true)} />

            <main>
                <section className="relative overflow-hidden border-b border-slate-800/70">
                    <div className="absolute inset-0 bg-[radial-gradient(circle_at_75%_20%,rgba(79,70,229,0.18),transparent_35%)]" />
                    <div className="relative mx-auto grid max-w-6xl gap-10 px-4 py-14 sm:px-6 sm:py-20 lg:grid-cols-[1.1fr_0.9fr] lg:items-center">
                        <div>
                            <div className="inline-flex rounded-full border border-emerald-800/70 bg-emerald-950/30 px-3 py-1 text-xs font-medium text-emerald-300">
                                Selected options opportunities · Paper tracked
                            </div>
                            <h1 className="mt-5 max-w-3xl text-4xl font-bold leading-[1.08] tracking-tight sm:text-5xl lg:text-6xl">
                                Keep the excitement.<br /><span className="text-indigo-300">Add a plan.</span>
                            </h1>
                            <p className="mt-5 max-w-2xl text-base leading-7 text-slate-300 sm:text-lg">
                                Quantelle brings selected options opportunities into focus with a specific contract, entry conditions, stop, targets, and updates as the trade develops. Follow the reasoning and see how each published plan plays out in paper trading.
                            </p>
                            <div className="mt-7 flex flex-wrap gap-3">
                                <a href="/signals" className="rounded-xl bg-indigo-600 px-5 py-3 font-semibold text-white shadow-lg shadow-indigo-950/40 hover:bg-indigo-500">
                                    Explore trade plans
                                </a>
                                <a href="/signals?view=completed" className="rounded-xl border border-sky-700 bg-sky-950/40 px-5 py-3 font-semibold text-sky-200 hover:bg-sky-950/70">
                                    See paper results
                                </a>
                            </div>
                            <p className="mt-4 text-xs text-slate-400">Browse the public record free · Active details may require Pro · No brokerage connection needed</p>
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
                                    <div className="text-xs uppercase tracking-wide text-slate-400">Before entry</div>
                                    <div className="mt-2 font-medium">Contract, trigger, and do-not-chase level</div>
                                </div>
                                <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-4">
                                    <div className="text-xs uppercase tracking-wide text-slate-400">Defined risk</div>
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
                        <div className="text-xs font-semibold uppercase tracking-[0.16em] text-indigo-300">How you use Quantelle</div>
                        <h2 className="mt-2 text-3xl font-bold tracking-tight">An opportunity you can understand and follow</h2>
                        <p className="mt-3 leading-7 text-slate-400">A clear plan gives you something specific to evaluate—and a record you can return to.</p>
                    </div>
                    <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
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
                    <div className="mx-auto grid max-w-6xl gap-8 px-4 py-14 sm:px-6 md:grid-cols-2 md:items-center">
                        <div>
                            <div className="text-xs font-semibold uppercase tracking-[0.16em] text-cyan-300">The paper trade record</div>
                            <h2 className="mt-3 text-3xl font-bold">See what happened next.</h2>
                            <p className="mt-4 leading-7 text-slate-300">Every completed trade has an outcome. Explore the original idea, the updates, and the realized paper result—including losses.</p>
                            <p className="mt-3 text-sm leading-6 text-slate-400">This selected QCOM trade shows how a completed result is presented. View the complete record to put it in context. Paper results are not expected real-money returns.</p>
                            <a href="/signals?view=completed" className="mt-6 inline-block rounded-xl border border-indigo-500/60 px-5 py-3 font-semibold text-indigo-200 hover:bg-indigo-950/50">See all completed trades</a>
                        </div>
                        <figure>
                            <img src="/images/qcom-paper-trade.webp" width="1200" height="1200" loading="lazy" decoding="async" alt="Selected completed QCOM paper trade: 58.76% realized return, $8.85 fill, $6.25 published stop, and $14.05 exit on September 25, 2026." className="mx-auto w-full max-w-md rounded-3xl border border-slate-700" />
                            <figcaption className="mt-3 text-center text-xs text-slate-400">Selected completed paper trade · Full history includes losing trades.</figcaption>
                        </figure>
                    </div>
                </section>
                <section className="mx-auto max-w-6xl px-4 py-14 sm:px-6">
                    <h2 className="text-3xl font-bold">Learn through the trades.</h2>
                    <p className="mt-3 leading-7 text-slate-400">Start with the plan, then explore the decisions behind it.</p>
                    <div className="mt-7 grid gap-4 md:grid-cols-3">
                        {guides.map((guide) => <a key={guide.slug} href={`/articles/${guide.slug}`} className="rounded-2xl border border-slate-800 bg-slate-900/45 p-6 transition hover:border-indigo-500/60">
                            <h3 className="text-lg font-semibold text-white">{guide.title}</h3>
                            <p className="mt-3 text-sm leading-6 text-slate-400">{guide.copy}</p>
                            <span className="mt-5 inline-block text-sm font-semibold text-indigo-300">Read the guide →</span>
                        </a>)}
                    </div>
                    <a href="/articles" className="mt-6 inline-block text-sm font-semibold text-indigo-300">Explore all articles →</a>
                </section>
                <section className="border-t border-slate-800 bg-indigo-950/20">
                    <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-12 sm:px-6 md:flex-row md:items-center md:justify-between">
                        <div><h2 className="text-2xl font-bold">Follow the next published plan.</h2><p className="mt-3 text-slate-300">Get Quantelle trade alerts on Telegram. Complimentary early access.</p></div>
                        <a href="https://t.me/+6zJGLH-XJWY0MTcx" target="_blank" rel="noreferrer" className="self-start whitespace-nowrap rounded-xl bg-sky-600 px-5 py-3 font-semibold text-white hover:bg-sky-500">Join trade alerts</a>
                    </div>
                </section>
                <p className="mx-auto max-w-6xl px-4 py-6 text-xs leading-5 text-slate-400 sm:px-6">Research and education only. Options can lose their entire premium. A planned stop does not guarantee an exit price. Paper results can differ from real execution.</p>

            </main>

            <SiteFooter />
            {signInOpen && <dialog ref={dialogRef} onClose={() => setSignInOpen(false)} onClick={(event) => {
                if (event.target === event.currentTarget) event.currentTarget.close();
            }} aria-label="Quantelle sign in" className="m-auto max-h-[calc(100dvh-2rem)] w-[calc(100%-2rem)] max-w-md overflow-y-auto rounded-2xl border border-slate-700 bg-slate-950 p-2 text-slate-100 shadow-2xl shadow-black/60 backdrop:bg-slate-950/80">
                <div className="mb-1 flex justify-end">
                    <button type="button" onClick={() => dialogRef.current?.close()} aria-label="Close sign in" className="rounded-md px-3 py-1 text-xl text-slate-400 hover:bg-slate-800 hover:text-white">×</button>
                </div>
                <Login />
            </dialog>}
        </div>
    );
}
