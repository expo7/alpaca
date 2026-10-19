from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone as django_timezone
from rest_framework.test import APITestCase

from .models import BillingProfile, TradeSignal


User = get_user_model()


@override_settings(
    STRIPE_SECRET_KEY="sk_test_example",
    STRIPE_PUBLISHABLE_KEY="pk_test_example",
    STRIPE_WEBHOOK_SECRET="whsec_example",
    STRIPE_PRICE_ID="price_test_pro",
    STRIPE_APP_URL="https://quantelle.io",
)
class BillingApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user("subscriber", email="subscriber@example.com", password="test-password")
        self.client.force_authenticate(self.user)

    def test_status_creates_inactive_profile(self):
        response = self.client.get("/api/billing/status/")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["is_pro"])
        self.assertEqual(response.data["status"], "inactive")

    @patch("ranker.views.stripe.checkout.Session.create")
    def test_checkout_uses_server_config_and_user_metadata(self, create_session):
        create_session.return_value = SimpleNamespace(url="https://checkout.stripe.test/session")
        response = self.client.post("/api/billing/checkout/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["url"], "https://checkout.stripe.test/session")
        kwargs = create_session.call_args.kwargs
        self.assertEqual(kwargs["mode"], "subscription")
        self.assertEqual(kwargs["line_items"], [{"price": "price_test_pro", "quantity": 1}])
        self.assertEqual(kwargs["metadata"]["user_id"], str(self.user.pk))
        self.assertNotIn("price", self.client.post.__dict__)

    @patch("ranker.views.stripe.billing_portal.Session.create")
    def test_customer_can_open_portal(self, create_session):
        BillingProfile.objects.create(user=self.user, stripe_customer_id="cus_test", status="active")
        create_session.return_value = SimpleNamespace(url="https://billing.stripe.test/portal")
        response = self.client.post("/api/billing/portal/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(create_session.call_args.kwargs["customer"], "cus_test")

    @patch("ranker.views.stripe.Subscription.retrieve")
    @patch("ranker.views.stripe.Webhook.construct_event")
    def test_signed_checkout_webhook_grants_access(self, construct_event, retrieve):
        profile = BillingProfile.objects.create(user=self.user)
        construct_event.return_value = {
            "type": "checkout.session.completed",
            "data": {"object": {
                "customer": "cus_test",
                "subscription": "sub_test",
                "client_reference_id": str(self.user.pk),
                "metadata": {"user_id": str(self.user.pk)},
            }},
        }
        retrieve.return_value = {
            "id": "sub_test",
            "customer": "cus_test",
            "status": "active",
            "metadata": {"user_id": str(self.user.pk)},
            "cancel_at_period_end": False,
            "current_period_end": int(datetime(2026, 10, 15, tzinfo=timezone.utc).timestamp()),
            "items": {"data": [{"price": {"id": "price_test_pro"}}]},
        }
        response = self.client.post(
            "/api/billing/webhook/",
            data=b"{}",
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="signed",
        )
        self.assertEqual(response.status_code, 200)
        profile.refresh_from_db()
        self.assertEqual(profile.status, "active")
        self.assertTrue(profile.has_pro_access)

    def _create_active_signal(self):
        return TradeSignal.objects.create(
            symbol="NVDA",
            company_name="NVIDIA Corporation",
            instrument_type="call",
            strike="240",
            expiration="2026-10-16",
            status=TradeSignal.STATUS_PUBLISHED,
            risk_level="high",
            entry_low="1.00",
            entry_high="1.25",
            initial_stop="0.65",
            target_1="1.75",
            thesis="Private thesis",
        )

    def test_active_signal_is_public_while_pro_gate_is_disabled(self):
        self._create_active_signal()
        response = self.client.get("/api/trade-signals/")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data[0]["is_locked"])
        self.assertEqual(response.data[0]["thesis"], "Private thesis")

    @patch("ranker.views.get_paper_position", return_value={"available": False})
    @patch("ranker.views.get_trade_signal_quote", return_value={"available": True})
    def test_active_signal_quote_is_public_while_pro_gate_is_disabled(self, _quote, _position):
        signal = self._create_active_signal()
        self.client.force_authenticate(user=None)
        response = self.client.get(f"/api/trade-signals/{signal.pk}/quote/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["available"])

    @override_settings(PRO_GATE_ENABLED=True)
    def test_active_signal_quote_requires_pro_when_gate_enabled(self):
        signal = self._create_active_signal()
        self.client.force_authenticate(user=None)
        response = self.client.get(f"/api/trade-signals/{signal.pk}/quote/")
        self.assertEqual(response.status_code, 403)

    @override_settings(PRO_GATE_ENABLED=True)
    def test_active_signal_is_redacted_until_subscription_is_active_when_gate_enabled(self):
        self._create_active_signal()
        response = self.client.get("/api/trade-signals/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data[0]["is_locked"])
        self.assertNotIn("thesis", response.data[0])

        BillingProfile.objects.create(user=self.user, status="active")
        response = self.client.get("/api/trade-signals/")
        self.assertFalse(response.data[0]["is_locked"])
        self.assertEqual(response.data[0]["thesis"], "Private thesis")
