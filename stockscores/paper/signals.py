from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import PaperPortfolio


@receiver(post_save, sender=get_user_model())
def create_default_portfolio(sender, instance, created, **kwargs):
    """
    Ensure every new user starts with a default paper portfolio.
    """
    if not created:
        return

    # Defensive: if something pre-created a portfolio (fixtures), skip duplicates
    if instance.paper_portfolios.exists():
        return

    PaperPortfolio.objects.create(
        user=instance,
        name="Default",
        base_currency="USD",
        status="active",
        starting_balance=Decimal("100000"),
        cash_balance=Decimal("100000"),
        equity=Decimal("100000"),
    )
