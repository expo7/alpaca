import { useState } from "react";
import { APP_NAME, APP_TAGLINE } from "../brand";

const tabs = [
  { id: "dashboard", label: "Dashboard" },
  { id: "macro", label: "Macro" },
  { id: "watchlists", label: "Watchlists" },
  { id: "alerts", label: "Alerts" },
  { id: "orders", label: "Orders" },
  { id: "positions", label: "Positions" },
  { id: "performance", label: "Performance" },
  { id: "leaderboards", label: "Leaderboards" },
  { id: "bots", label: "Bots" },
  { id: "backtest-history", label: "Backtest History" },
  { id: "settings", label: "Settings" },
  { id: "strategy-backtest", label: "Backtest (Exp)" },
  { id: "strategies", label: "Strategies" },
];

const V1_TABS = [
  { id: "dashboard", label: "Today" },
  { id: "signals", label: "Live Options" },
  { id: "billing", label: "Pro" },
  { id: "opportunities", label: "Opportunities" },
  { id: "articles", label: "Articles" },
];

export default function Navbar({
  isAuthed = false,
  user,
  active,
  onNavigate,
  onLogout,
  v1Mode = false,
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const baseTabs = v1Mode ? V1_TABS : tabs;
  const visibleTabs = user?.is_staff || user?.is_superuser
    ? [...baseTabs, { id: "analytics", label: "Analytics" }]
    : baseTabs;

  function navigate(tabId) {
    onNavigate(tabId);
    setMenuOpen(false);
  }

  const renderTabs = (className) => visibleTabs.map((tab) => (
    <button
      key={tab.id}
      type="button"
      onClick={() => navigate(tab.id)}
      className={`${className} ${
        active === tab.id
          ? "bg-indigo-500/15 text-indigo-200"
          : "text-slate-400 hover:bg-slate-900 hover:text-slate-100"
      }`}
    >
      {tab.label}
    </button>
  ));

  return (
    <header className="navbar relative w-full border-b border-slate-800 bg-slate-950/80 backdrop-blur">
      <div className="mx-auto w-full max-w-7xl px-4 sm:px-6">
        <div className="flex min-h-16 items-center justify-between gap-4">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex min-w-0 flex-col">
              <span className="truncate text-[0.78rem] font-black tracking-[0.14em] text-white">
                {APP_NAME.toUpperCase()}
              </span>
              <span className="hidden text-xs text-slate-500 min-[1350px]:block">
                {APP_TAGLINE}
              </span>
            </div>

            <nav
              aria-label="Primary navigation"
              className="hidden min-[1350px]:flex min-[1350px]:items-center min-[1350px]:gap-1"
            >
              {renderTabs("rounded-md px-2 py-2 text-xs transition")}
            </nav>
          </div>

          <div className="flex shrink-0 items-center gap-2 text-xs sm:gap-3">
            {isAuthed ? (
              <>
                {user && (
                  <div className="hidden flex-col items-end leading-tight min-[1350px]:flex">
                    <span className="font-medium text-slate-200">
                      {user.username || user.email || "User"}
                    </span>
                    {user.email && (
                      <span className="text-slate-500">{user.email}</span>
                    )}
                  </div>
                )}
                <button
                  type="button"
                  onClick={onLogout}
                  className="rounded-md border border-slate-700 px-3 py-1.5 text-xs text-slate-200 transition hover:bg-slate-800"
                >
                  Log out
                </button>
              </>
            ) : (
              <a
                href="/"
                className="rounded-md border border-slate-700 px-3 py-1.5 text-xs text-slate-200 transition hover:bg-slate-800"
              >
                Sign in / Create account
              </a>
            )}
            <button
              type="button"
              aria-controls="navbar-menu"
              aria-expanded={menuOpen}
              aria-label={menuOpen ? "Close navigation menu" : "Open navigation menu"}
              onClick={() => setMenuOpen((isOpen) => !isOpen)}
              className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-slate-700 text-slate-300 transition hover:bg-slate-800 min-[1350px]:hidden"
            >
              <span aria-hidden="true" className="text-lg leading-none">
                {menuOpen ? "×" : "☰"}
              </span>
            </button>
          </div>
        </div>
      </div>

      {menuOpen && (
        <nav
          id="navbar-menu"
          aria-label="Navigation menu"
          className="border-t border-slate-800 bg-slate-950/95 px-4 py-3 backdrop-blur sm:px-6 min-[1350px]:hidden"
        >
          <div className="mx-auto grid w-full max-w-7xl grid-cols-2 gap-1 sm:grid-cols-3">
            {renderTabs("rounded-md px-3 py-2 text-left text-xs transition")}
          </div>
        </nav>
      )}
    </header>
  );
}
