// ==============================
// File: src/components/Navbar.jsx
// Simple top nav using page + onNavigate, no react-router
// ==============================

import Logo from "./Logo.jsx";

const tabs = [
  { id: "dashboard", label: "Dashboard" },
  { id: "watchlists", label: "Watchlists" },
  { id: "alerts", label: "Alerts" },
  { id: "orders", label: "Orders" },
  { id: "performance", label: "Performance" },
  { id: "leaderboards", label: "Leaderboards" },
  { id: "settings", label: "Settings" },
  { id: "backtests", label: "Backtests" },
  { id: "strategies", label: "Strategies" },
];

export default function Navbar({ user, active, onNavigate, onLogout }) {
  return (
    <header className="border-b border-slate-800 bg-slate-950/80 backdrop-blur">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3 flex items-center justify-between gap-4">
        {/* Left: logo + brand */}
        <div className="flex items-center gap-3">
          <Logo className="w-8 h-8" />
          <div className="flex flex-col">
            <span className="text-sm font-semibold tracking-wide">
              Stock Ranker
            </span>
            <span className="text-xs text-slate-400">
              Tech + fundamentals, one score.
            </span>
          </div>
        </div>

        {/* Center: nav tabs */}
        <nav className="hidden md:flex items-center gap-2 text-sm">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => onNavigate(tab.id)}
              className={`px-3 py-1.5 rounded-full border text-xs transition
                ${
                  active === tab.id
                    ? "bg-indigo-600/90 border-indigo-500 text-white shadow-sm"
                    : "bg-slate-900 border-slate-700 text-slate-300 hover:bg-slate-800"
                }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>

        {/* Right: user + logout */}
        <div className="flex items-center gap-3 text-xs">
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
        </div>
      </div>

      {/* Mobile nav row */}
      <div className="md:hidden border-t border-slate-800 px-3 py-2 flex gap-2 overflow-x-auto text-xs">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => onNavigate(tab.id)}
            className={`px-3 py-1.5 rounded-full border whitespace-nowrap ${
              active === tab.id
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
