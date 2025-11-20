# Paper Trading Services & Background Jobs

The Django app now produces portfolio performance snapshots and paper-trading leaderboards on a schedule. To keep those datasets fresh outside of local development you **must** run the Celery worker and Celery beat service alongside `manage.py runserver`.

## Required processes

```bash
# API / admin
python manage.py runserver

# Celery worker (handles execution, strategy engines, etc.)
celery -A stockscores worker -l info

# Celery beat (fires periodic tasks for algos, snapshots, leaderboards)
celery -A stockscores beat -l info
```

The beat schedule (configured in `stockscores/stockscores/settings.py`) includes:

| Task | Purpose | Interval |
| --- | --- | --- |
| `paper.tasks.run_algo_slices` | advances TWAP/VWAP/POV orders | 60s |
| `paper.tasks.snapshot_portfolios` | records daily equity/cash snapshots | 5 min |
| `paper.tasks.recompute_leaderboards` | recalculates leaderboard metrics | 30 min |

If either the worker or beat service is missing, the React “Performance” and “Leaderboards” pages will appear empty because no new data is captured.
