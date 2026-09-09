import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "stockscores.settings")

app = Celery("stockscores")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
app.conf.beat_schedule.setdefault(
    "ranker-paper-trade-executor",
    {
        "task": "ranker.tasks.run_paper_trade_executor",
        "schedule": 15.0,
    },
)


@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
