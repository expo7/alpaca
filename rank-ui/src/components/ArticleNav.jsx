import { APP_NAME } from "../brand";

export default function ArticleNav({ isAuthed, user, onNavigateDashboard, onNavigateAnalytics, onLogout, onSignUp, onLogIn }) {
    return (
        <header className="border-b border-slate-800 bg-slate-950/80 backdrop-blur sticky top-0 z-40">
            <div className="max-w-6xl mx-auto px-4 sm:px-6 py-3 flex items-center justify-between">
                {/* Left: Brand */}
                <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-xl bg-indigo-600 flex items-center justify-center text-xs font-bold">
                        Q
                    </div>
                    <div className="flex flex-col">
                        <span className="text-sm font-semibold tracking-wide">
                            {APP_NAME}
                        </span>
                        <span className="text-xs text-slate-400">Daily market decisions</span>
                    </div>
                </div>

                {/* Right: Nav + Auth */}
                <nav className="flex items-center gap-4 sm:gap-6 text-sm">
                    <a href="/articles" className="text-slate-300 hover:text-white transition">
                        Articles
                    </a>

                    {isAuthed ? (
                        <>
                            <button
                                type="button"
                                onClick={onNavigateDashboard}
                                className="text-slate-300 hover:text-white transition"
                            >
                                Dashboard
                            </button>
                            {(user?.is_staff || user?.is_superuser) && (
                                <button
                                    type="button"
                                    onClick={onNavigateAnalytics}
                                    className="text-slate-300 hover:text-white transition"
                                >
                                    Analytics
                                </button>
                            )}
                            <div className="hidden sm:flex items-center gap-2 text-xs">
                                <span className="text-slate-500">{user?.username || user?.email || "User"}</span>
                                <button
                                    type="button"
                                    onClick={onLogout}
                                    className="text-slate-400 hover:text-slate-200 transition"
                                >
                                    Log out
                                </button>
                            </div>
                        </>
                    ) : (
                        <div className="hidden sm:flex items-center gap-2 text-xs">
                            <button
                                type="button"
                                onClick={onLogIn}
                                className="text-slate-300 hover:text-white transition"
                            >
                                Log in
                            </button>
                            <button
                                type="button"
                                onClick={onSignUp}
                                className="px-3 py-1.5 rounded-full bg-indigo-600 hover:bg-indigo-500 transition text-white"
                            >
                                Sign up
                            </button>
                        </div>
                    )}
                </nav>
            </div>
        </header>
    );
}
