from django.apps import AppConfig


class RankerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ranker'

    def ready(self):
        # Register lifecycle/outbox receivers and Telegram Celery tasks.
        from . import signals, telegram, sitemap_signals  # noqa: F401
