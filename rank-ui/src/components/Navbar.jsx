// ==============================
// File: src/components/Navbar.jsx
// Simple top nav using page + onNavigate, no react-router
// ==============================

import Logo from "./Logo.jsx";
import { APP_NAME } from "../brand";

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
  const baseTabs = v1Mode ? V1_TABS : tabs;
  const visibleTabs = user?.is_staff || user?.is_superuser
    ? [...baseTabs, { id: "analytics", label: "Analytics" }]
    : baseTabs;

  return (
    <header className="navbar border-b border-slate-800 bg-slate-950/80 backdrop-blur w-full">
      <div className="w-full max-w-7xl mx-auto px-4 sm:px-6 py-3 flex items-center justify-between gap-4 flex-wrap">
        {/* Left: logo + brand */}
        <div className="flex items-center gap-3">
          <Logo className="w-8 h-8" />
          <div className="flex flex-col">
            <span className="text-sm font-semibold tracking-wide">
              {APP_NAME}
            </span>
            <span className="text-xs text-slate-400">
              Tech + fundamentals, one rating.
            </span>
          </div>
        </div>

        {/* Center: nav tabs — hidden in V1 (single page) */}
        <nav className="hidden md:flex items-center gap-2 text-sm">
          {visibleTabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => onNavigate(tab.id)}
              className={`px-3 py-1.5 rounded-full border text-xs transition
                ${active === tab.id
                  ? "bg-indigo-600/90 border-indigo-500 text-white shadow-sm"
                  : "bg-slate-900 border-slate-700 text-slate-300 hover:bg-slate-800"
                }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>

        {/* Right: auth state */}
        <div className="flex items-center gap-3 text-xs">
          {isAuthed ? (
            <>
              {user && (
                <div className="hidden sm:flex flex-col items-end leading-tight">
                  <span className="text-slate-200 font-medium">
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
                className="px-3 py-1.5 rounded-full border border-slate-700 text-slate-200 hover:bg-slate-800 text-xs"
              >
                Log out
              </button>
            </>
          ) : (
            <a
              href="/"
              className="px-3 py-1.5 rounded-full border border-slate-700 text-slate-200 hover:bg-slate-800 text-xs"
            >
              Sign in / Create account
            </a>
          )}
        </div>
      </div>

      {/* Mobile nav row */}
      <div className="md:hidden border-t border-slate-800 px-3 py-2 flex gap-2 overflow-x-auto text-xs">
        {visibleTabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => onNavigate(tab.id)}
            className={`px-3 py-1.5 rounded-full border whitespace-nowrap ${active === tab.id
              ? "bg-indigo-600/90 border-indigo-500 text-white"
              : "bg-slate-900 border-slate-700 text-slate-300 hover:bg-slate-800"
              }`}
          >
            {tab.label}
          </button>
        ))}
      </div>
    </header>
  );
}
