import { useCallback, useEffect, useMemo, useState } from "react";
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

function slugify(value) {
    return (value || "")
        .toLowerCase()
        .trim()
        .replace(/[^a-z0-9\s-]/g, "")
        .replace(/\s+/g, "-")
        .replace(/-+/g, "-");
}

export default function ArticlesListPage({
    apiBase,
    token,
    isAuthed,
    user,
    onOpenArticle,
    onNavigateDashboard,
    onLogout,
    onSignUp,
    onLogIn,
}) {
    const [articles, setArticles] = useState([]);
    const [loading, setLoading] = useState(true);
    const [err, setErr] = useState("");

    const [title, setTitle] = useState("");
    const [slug, setSlug] = useState("");
    const [content, setContent] = useState("");
    const [creating, setCreating] = useState(false);
    const [createErr, setCreateErr] = useState("");

    const suggestedSlug = useMemo(() => slugify(title), [title]);

    const fetchArticles = useCallback(async () => {
        setLoading(true);
        setErr("");
        try {
            const res = await fetch(`${apiBase}/api/articles/`);
            const json = await res.json().catch(() => []);
            if (!res.ok) throw new Error(json?.detail || "Failed to load articles.");
            setArticles(Array.isArray(json) ? json : []);
        } catch (e) {
            setErr(e?.message || "Failed to load articles.");
        } finally {
            setLoading(false);
        }
    }, [apiBase]);

    useEffect(() => {
        fetchArticles();
    }, [fetchArticles]);

    async function createArticle(e) {
        e.preventDefault();
        if (!token) {
            setCreateErr("Sign in required to create an article.");
            return;
        }

        setCreating(true);
        setCreateErr("");
        try {
            const payload = {
                title: title.trim(),
                slug: (slug || suggestedSlug).trim(),
                content: content.trim(),
            };
            const res = await fetch(`${apiBase}/api/articles/`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    Authorization: `Bearer ${token}`,
                },
                body: JSON.stringify(payload),
            });
            const json = await res.json().catch(() => ({}));
            if (!res.ok) {
                const firstError =
                    typeof json === "object"
                        ? Object.values(json)?.flat?.()?.[0] || json.detail
                        : "Create failed.";
                throw new Error(String(firstError || "Create failed."));
            }
            setTitle("");
            setSlug("");
            setContent("");
            await fetchArticles();
            onOpenArticle(json.slug);
        } catch (e) {
            setCreateErr(e?.message || "Create failed.");
        } finally {
            setCreating(false);
        }
    }

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

            <main className="flex-1 max-w-3xl mx-auto w-full px-4 sm:px-6 py-10 space-y-8">
                <header className="space-y-2">
                    <h1 className="text-2xl sm:text-3xl font-semibold">Articles</h1>
                    <p className="text-sm text-slate-400">Simple public reads from the Quantelle team.</p>
                </header>

                {isAuthed && (
                    <section className="border border-slate-700 rounded-lg p-6 bg-slate-900/50">
                        <h2 className="text-base font-semibold mb-4">Create article</h2>
                        <form className="space-y-4" onSubmit={createArticle}>
                            <div>
                                <label className="block text-xs font-medium text-slate-300 mb-2">Title</label>
                                <input
                                    value={title}
                                    onChange={(e) => setTitle(e.target.value)}
                                    required
                                    className="w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                                    placeholder="Article title"
                                />
                            </div>
                            <div>
                                <label className="block text-xs font-medium text-slate-300 mb-2">URL slug (optional)</label>
                                <input
                                    value={slug}
                                    onChange={(e) => setSlug(e.target.value)}
                                    className="w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                                    placeholder={suggestedSlug || "auto-generated-from-title"}
                                />
                            </div>
                            <div>
                                <label className="block text-xs font-medium text-slate-300 mb-2">Content</label>
                                <textarea
                                    value={content}
                                    onChange={(e) => setContent(e.target.value)}
                                    required
                                    rows={10}
                                    className="w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                                    placeholder="Write your article..."
                                />
                            </div>
                            {createErr && <p className="text-xs text-rose-300">{createErr}</p>}
                            <button
                                type="submit"
                                disabled={creating}
                                className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-sm font-medium transition"
                            >
                                {creating ? "Publishing..." : "Publish"}
                            </button>
                        </form>
                    </section>
                )}

                <section className="space-y-3">
                    {loading && <p className="text-sm text-slate-400">Loading articles...</p>}
                    {err && <p className="text-sm text-rose-300">{err}</p>}
                    {!loading && !err && articles.length === 0 && (
                        <p className="text-sm text-slate-400">No articles published yet.</p>
                    )}
                    {!loading && !err && articles.map((article) => (
                        <article key={article.slug} className="border border-slate-700 rounded-lg p-5 bg-slate-900/40 hover:bg-slate-900/60 transition">
                            <button
                                type="button"
                                onClick={() => onOpenArticle(article.slug)}
                                className="text-left w-full"
                            >
                                <h3 className="text-lg font-medium hover:text-indigo-300 transition">{article.title}</h3>
                            </button>
                            <p className="text-xs text-slate-400 mt-2">{formatDate(article.created_at)}</p>
                        </article>
                    ))}
                </section>

                <ArticleCTA
                    isAuthed={isAuthed}
                    onViewDashboard={onNavigateDashboard}
                    onSignUp={onSignUp}
                />
            </main>
        </div>
    );
}
