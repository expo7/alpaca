# Frontend overview

Stack and entry points
- React + Vite (no react-router; tabbed navigation driven by `page` state in `src/App.jsx`).
- Auth context in `src/AuthProvider.jsx` stores JWT/user in `localStorage`; `src/main.jsx` wraps `<App />` in `<AuthProvider>`.
- Global styles in `src/index.css`, Vite config in `vite.config.js`.

Primary views (rendered from `App.jsx` via `<Navbar>` tabs)
- `dashboard` (ranking + ticker inputs) plus watchlist save modal inline.
- `orders` (`src/pages/Orders.jsx`): order list/editor, audit modal with pinned timeline, queue/ETA chips, override modal.
- `positions` (`src/pages/Positions.jsx`): paginated positions with live quotes, cap warnings, close/rebalance actions.
- `performance` (`src/pages/Performance.jsx`): portfolio metrics, snapshots sparkline, deposits/withdrawals.
- `leaderboards` (`src/pages/Leaderboards.jsx`): seasons + metric filters, leaderboard table.
- `watchlists`, `alerts`, `settings`, `backtests`, `strategies` (`src/pages/StrategyBuilder.jsx`), plus `Landing` when unauthenticated.

Strategy builder & execution
- Endpoints used: `GET/POST/PUT /api/paper/strategies/`, `POST /api/paper/strategies/validate_config/`, `POST /api/paper/strategies/dry_run/`, and `POST /api/paper/strategies/{id}/execute/`.
- Strategy state includes symbols, rule trees, order templates, and portfolio targets (single or multi); caps are pre-checked client-side and enforced server-side.
- Execution UI posts `{strategy_id, portfolio_ids, overrides?}` and shows queued status/ID from the response.

API access patterns
- `BASE` is hard-coded to `http://127.0.0.1:8000` (switch to a Vite proxy by setting `BASE = ""`).
- Most pages define a small `apiFetch` helper that attaches `Authorization: Bearer <token>` when present and parses JSON.
- Additional endpoints in use: portfolios (`/api/paper/portfolios/`), positions (`/api/paper/positions/`), quotes (`/api/paper/quotes/`), audits (`/api/paper/orders/{id}/audit/`, `/api/paper/positions/{id}/audit/`), instruments lookup, performance snapshots, leaderboards, and watchlists.
