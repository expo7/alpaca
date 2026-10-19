from datetime import datetime, timezone as dt_timezone

import stripe
from django.conf import settings
from django.db import transaction

from .models import BillingProfile


class BillingConfigurationError(RuntimeError):
    pass


def stripe_ready(*, require_webhook=False):
    values = [settings.STRIPE_SECRET_KEY, settings.STRIPE_PRICE_ID]
    if require_webhook:
        values.append(settings.STRIPE_WEBHOOK_SECRET)
    return all(values)


def require_stripe_config(*, require_webhook=False):
    if not stripe_ready(require_webhook=require_webhook):
        raise BillingConfigurationError("Stripe billing is not configured")
    stripe.api_key = settings.STRIPE_SECRET_KEY


def get_billing_profile(user):
    profile, _ = BillingProfile.objects.get_or_create(user=user)
    return profile


def user_has_pro_access(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    try:
        return user.billing_profile.has_pro_access
    except BillingProfile.DoesNotExist:
        return False


def _timestamp(value):
    if not value:
        return None
    return datetime.fromtimestamp(int(value), tz=dt_timezone.utc)


def _value(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def sync_subscription(subscription, *, user=None):
    """Idempotently mirror the Stripe subscription state into our database."""
    subscription_id = _value(subscription, "id", "")
    customer_id = _value(subscription, "customer", "")
    metadata = _value(subscription, "metadata", {}) or {}
    user_id = metadata.get("user_id") if hasattr(metadata, "get") else None

    with transaction.atomic():
        profile = None
        if subscription_id:
            profile = BillingProfile.objects.select_for_update().filter(
                stripe_subscription_id=subscription_id
            ).first()
        if profile is None and customer_id:
            profile = BillingProfile.objects.select_for_update().filter(
                stripe_customer_id=customer_id
            ).first()
        if profile is None and user is not None:
            profile, _ = BillingProfile.objects.select_for_update().get_or_create(user=user)
        if profile is None and user_id:
            profile, _ = BillingProfile.objects.select_for_update().get_or_create(user_id=user_id)
        if profile is None:
            return None

        items = _value(_value(subscription, "items", {}), "data", []) or []
        first_item = items[0] if items else {}
        price = _value(first_item, "price", {}) or {}
        period_end = _value(subscription, "current_period_end") or _value(first_item, "current_period_end")

        profile.stripe_customer_id = customer_id or profile.stripe_customer_id
        profile.stripe_subscription_id = subscription_id or profile.stripe_subscription_id
        profile.stripe_price_id = _value(price, "id", "") or profile.stripe_price_id
        profile.status = _value(subscription, "status", "inactive")
        profile.current_period_end = _timestamp(period_end)
        profile.cancel_at_period_end = bool(_value(subscription, "cancel_at_period_end", False))
        profile.save()
        return profile


def billing_payload(user):
    profile = get_billing_profile(user)
    return {
        "configured": stripe_ready(),
        "publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
        "price_id": settings.STRIPE_PRICE_ID,
        "is_pro": profile.has_pro_access,
        "status": profile.status,
        "current_period_end": profile.current_period_end,
        "cancel_at_period_end": profile.cancel_at_period_end,
        "has_customer": bool(profile.stripe_customer_id),
    }
