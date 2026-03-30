import { useEffect, useState } from "react";
import ArticleNav from "../components/ArticleNav.jsx";
import ArticleCTA from "../components/ArticleCTA.jsx";

function formatDate(ts) {
    if (!ts) return "";
    const d = new Date(ts);
    if (Number.isNaN(d.getTime())) return "";
    return d.toLocaleDateString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
    });
}

export default function ArticleDetailPage({
    apiBase,
    slug,
    isAuthed,
    user,
    onBackToArticles,
    onNavigateDashboard,
    onLogout,
    onSignUp,
    onLogIn,
}) {
    const [article, setArticle] = useState(null);
    const [loading, setLoading] = useState(true);
    const [err, setErr] = useState("");

    useEffect(() => {
        let alive = true;

        async function fetchArticle() {
            setLoading(true);
            setErr("");
            try {
                const res = await fetch(`${apiBase}/api/articles/${encodeURIComponent(slug)}/`);
                const json = await res.json().catch(() => ({}));
                if (!res.ok) throw new Error(json?.detail || "Failed to load article.");
                if (!alive) return;
                setArticle(json);
            } catch (e) {
                if (!alive) return;
                setErr(e?.message || "Failed to load article.");
            } finally {
                if (alive) setLoading(false);
            }
        }

        if (slug) fetchArticle();
        return () => {
            alive = false;
        };
    }, [apiBase, slug]);

    return (
        <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
            <ArticleNav
                isAuthed={isAuthed}
                user={user}
                onNavigateDashboard={onNavigateDashboard}
                onLogout={onLogout}
                onSignUp={onSignUp}
                onLogIn={onLogIn}
            />

            <main className="flex-1 max-w-3xl mx-auto w-full px-4 sm:px-6 py-10">
                <button
                    type="button"
                    onClick={onBackToArticles}
                    className="text-sm text-slate-400 hover:text-slate-200 mb-6"
                >
                    ← Back to articles
                </button>

                {loading && <p className="text-sm text-slate-400">Loading article...</p>}
                {err && <p className="text-sm text-rose-300">{err}</p>}

                {!loading && !err && article && (
                    <article className="space-y-8">
                        <header className="space-y-3 border-b border-slate-700 pb-6">
                            <h1 className="text-3xl sm:text-4xl font-bold leading-tight tracking-tight">{article.title}</h1>
                            <p className="text-sm text-slate-400">{formatDate(article.created_at)}</p>
                        </header>
                        <div className="prose prose-invert max-w-none prose-sm sm:prose-base whitespace-pre-wrap leading-8 text-slate-100 font-light">
                            {article.content}
                        </div>
                    </article>
                )}

                {!loading && !err && article && (
                    <ArticleCTA
                        isAuthed={isAuthed}
                        onViewDashboard={onNavigateDashboard}
                        onSignUp={onSignUp}
                    />
                )}
            </main>
        </div>
    );
}
