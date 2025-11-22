from django.apps import AppConfig


class PaperConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'paper'

    def ready(self):
        # Import signal handlers to wire user onboarding
        from . import signals  # noqa: F401
