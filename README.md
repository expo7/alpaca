# Quantelle

**Trading research with a visible trade record.** [quantelle.io](https://quantelle.io) connects market analysis to specific trade setups, follows pending and open positions, and preserves completed outcomes. The current execution integration uses **Alpaca paper trading**; the public record should not be mistaken for live-money performance.

## What the project does

- Publishes research articles, market context, and a macro dashboard.
- Presents trade setups with entry conditions, risk, targets, and lifecycle updates; groups open positions, pending entries, and completed history on the [Trade Record](https://quantelle.io/signals).
- Supports stock ranking, watchlists, alerts, strategy backtests, and paper-trading views.
- Uses background jobs for strategy execution, portfolio snapshots, and leaderboards.
- Sends configured trade-event notifications through Telegram, linking back to the relevant trade card.

The aim is an auditable record of decisions and outcomes, including trades that never fill or are cancelled. Features and signal availability can change as the product develops.

## Architecture

| Area | Implementation |
| --- | --- |
| Web interface | React, Vite (`rank-ui/`) |
| API and admin | Django, Django REST Framework (`stockscores/`) |
| Research and signals | `stockscores/ranker/`, `stockscores/macro/` |
| Paper-trading system | `stockscores/paper/`, Alpaca paper API integration |
| Scheduled work | Celery worker and beat, Redis |
| Persistent data | PostgreSQL |
| Production | Docker Compose behind a host reverse proxy; GitHub Actions deploys the `production` branch |

## Running locally

The repository contains both the API and frontend. You will need Python, Node.js, PostgreSQL, and Redis, or a suitable local container setup. External integrations need separate credentials. Never commit real credentials or enable paper order execution merely to browse the UI.

1. Create a local environment file from [`.env.example`](.env.example) and set the values appropriate to your machine. The Docker Compose services expect a local `.env.docker` file. Review the database URL, Django secret, allowed hosts, and optional service settings before starting containers.
2. From the repository root, start the backend and scheduled services with `docker compose up --build`. The API listens on `127.0.0.1:8000`; the compose setup also starts PostgreSQL, Redis, a Celery worker, and Celery beat. Database migrations run when the web container starts.
3. In a separate terminal, run `cd rank-ui && npm ci && npm run dev`. Vite proxies `/api` requests to the local backend. Open the URL Vite prints.

The supplied environment example uses production-oriented hostnames and placeholder credentials; adapt it for local development. Some market data, brokerage, email, billing, and notification flows require configured third-party accounts.

For frontend verification, use `cd rank-ui && npm test && npm run build`. Backend tests live in the Django apps under `stockscores/`.

### Background services

The worker processes execution and strategy jobs; beat schedules recurring jobs. Without both, portfolio performance snapshots and leaderboards will stop updating. The schedule is defined in `stockscores/stockscores/settings.py`, including algorithm slices, portfolio snapshots, and leaderboard recomputation.

## Deployment

The [production workflow](.github/workflows/deploy-production.yml) runs frontend tests and a build on pushes to `production`, then deploys that exact revision to the Docker host. It refuses to overwrite an unexpectedly modified server worktree and checks the internal trade-signals API and public Trade Record after deployment. Deployment credentials are held as GitHub Actions secrets; no secret values belong in this repository.

## Repository notes

[`alpaca.ipynb`](alpaca.ipynb) is an exploratory Alpaca notebook. Its generated results are cleared in Git so an asset listing does not dominate repository size or expose account output. Run it only with your own **paper** credentials and clear outputs before committing changes.

This project is under active development. Paper-trading results and research are presented for product transparency, not as a guarantee of future returns.
