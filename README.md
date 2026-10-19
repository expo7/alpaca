# Quantelle

[Quantelle](https://quantelle.io/) is a trading research and paper execution project. It brings market analysis, option trade ideas, published trade records, and portfolio tracking into one application. Trade ideas and paper execution are experiments; paper results are not real-money returns.

This repository contains the Django backend in `stockscores/` and the React/Vite interface in `rank-ui/`. PostgreSQL stores application data, Redis supports background work, and Celery worker and beat run scheduled jobs. The root `docker-compose.yml` describes a local development stack.

## Explore the project

- [Live website](https://quantelle.io/)
- [Frontend overview](docs/frontend_overview.md)
- [Backend application](stockscores/)
- [React interface](rank-ui/)
- [Continuous integration](.github/workflows/ci.yml)

## Local development

Use your own environment values and paper credentials. Do not put API keys or local environment files into commits. The Compose file starts `web`, `worker`, `beat`, PostgreSQL, and Redis; review its development settings before use. For a quick frontend check, run `npm ci` and `npm run dev` from `rank-ui/`.

The worker and beat are needed for scheduled paper-trading and performance tasks. These commands are for local development:

```bash
cd stockscores
python manage.py runserver
celery -A stockscores worker -l info
celery -A stockscores beat -l info
```

Repository code and the live service may differ by deployed revision. Verify the deployment before treating a local checkout as production state.

## Branches and deployment

`master` is the integration baseline and contains the production application plus current diagnostics. `production` identifies the tested release deployed on the server. Merge production fixes back into master; prepare future releases from master so fixes cannot remain stranded on the release branch.

The [production workflow](.github/workflows/deploy-production.yml) tests the frontend and backend, builds the image on GitHub's runner, and deploys pushes to `production`. A newer master revision is not automatically a production deployment. Verify the installed commit and broker protection after a release. Keep environment files and credentials out of Git.

The October 19 baseline reconciliation merges the installed `bb61c15` release into master without changing its application code, while preserving the newer read-only diagnostics and [trading reset procedure](docs/TRADING_RESET_V1.md).
