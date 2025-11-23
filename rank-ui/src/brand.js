// src/brand.js
export const APP_NAME = "Stock Ranker";
export const APP_TAGLINE = "Tech + fundamentals, one score.";
export const BRAND = {
  primary: "indigo", // Tailwind color token root (e.g. indigo, emerald, sky)
  // You can expand later (secondary, accents, etc.)
};

export const NAV_LINKS = [
  { label: "Dashboard", id: "dashboard" },
  { label: "Watchlists", id: "watchlists"}, // future
  { label: "Strategy Backtest (Exp)",  id: "strategy-backtest",  disabled: false }, // future
  { label: "Alerts",     id: "alerts",     disabled: false }, // future
  { label: "Settings",   id: "settings"   },
];
