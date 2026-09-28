import os
from unittest.mock import Mock, patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APITestCase

from .broker_sandbox import AUTH_URL, API_URL, BrokerSandboxClient


class BrokerSandboxTests(APITestCase):
    def setUp(self):
        self.account_id = uuid4()
        self.user = get_user_model().objects.create_superuser(username="broker-admin", password="secret", email="admin@example.com")
        self.client.force_authenticate(self.user)
        cache.clear()

    def test_token_exchange_and_reuse_for_read_only_calls(self):
        session = Mock()
        session.post.return_value = Mock(ok=True, json=lambda: {"access_token": "test-token", "expires_in": 899})
        session.request.return_value = Mock(ok=True, status_code=200, json=lambda: {"status": "ACTIVE"})
        with patch.dict(os.environ, {"ALPACA_BROKER_SANDBOX_API_KEY": "key", "ALPACA_BROKER_SANDBOX_API_SECRET": "secret"}):
            broker = BrokerSandboxClient(session=session)
            broker.account(self.account_id)
            broker.account(self.account_id)
        self.assertEqual(session.post.call_count, 1)
        self.assertEqual(session.post.call_args.args[0], AUTH_URL)
        self.assertEqual(session.post.call_args.kwargs["data"]["grant_type"], "client_credentials")
        self.assertEqual(session.request.call_args.args[1], f"{API_URL}/v1/trading/accounts/{self.account_id}/account")
        self.assertEqual(session.request.call_args.kwargs["headers"], {"Authorization": "Bearer test-token"})

    def test_only_superusers_can_see_or_send_orders(self):
        urls = (reverse("broker-sandbox"), reverse("broker-sandbox-account", args=[self.account_id]),
                reverse("broker-sandbox-order", args=[self.account_id]))
        self.user.is_superuser = False
        self.user.is_staff = True
        self.user.save(update_fields=["is_superuser", "is_staff"])
        for url in urls[:2]:
            self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(urls[2], {}).status_code, 403)
        self.client.force_authenticate(user=None)
        self.assertIn(self.client.get(urls[0]).status_code, (401, 403))

    def test_order_submission_is_off_by_default(self):
        with patch.dict(os.environ, {"ALPACA_BROKER_SANDBOX_ORDER_ENABLED": "false"}):
            response = self.client.post(reverse("broker-sandbox-order", args=[self.account_id]), {
                "symbol": "AAPL", "qty": "1", "limit_price": "100", "confirm": "SANDBOX BUY 1 AAPL",
            })
        self.assertEqual(response.status_code, 403)

    @patch("ranker.broker_sandbox_views.BrokerSandboxClient")
    def test_manual_trial_requires_confirmation_and_buying_power(self, client_class):
        client_class.return_value.account.return_value = {"status": "ACTIVE", "trading_blocked": False,
                                                       "non_marginable_buying_power": "0"}
        url = reverse("broker-sandbox-order", args=[self.account_id])
        payload = {"symbol": "AAPL", "qty": "1", "limit_price": "100", "confirm": "SANDBOX BUY 1 AAPL"}
        with patch.dict(os.environ, {"ALPACA_BROKER_SANDBOX_ORDER_ENABLED": "true"}):
            self.assertEqual(self.client.post(url, {**payload, "confirm": ""}).status_code, 400)
            self.assertEqual(self.client.post(url, payload).status_code, 409)
        client_class.return_value.submit_order.assert_not_called()

    @patch("ranker.broker_sandbox_views.BrokerSandboxClient")
    def test_cancel_only_own_open_trial_order(self, client_class):
        order_id = uuid4()
        url = reverse("broker-sandbox-cancel-order", args=[self.account_id, order_id])
        client_class.return_value.orders.return_value = [{"id": str(order_id), "client_order_id": "other-order", "status": "accepted"}]
        with patch.dict(os.environ, {"ALPACA_BROKER_SANDBOX_ORDER_ENABLED": "true"}):
            self.assertEqual(self.client.post(url, {"confirm": "CANCEL SANDBOX ORDER"}).status_code, 404)
            client_class.return_value.orders.return_value[0]["client_order_id"] = "quantelle-admin-sandbox-test"
            self.assertEqual(self.client.post(url, {}).status_code, 400)
            self.assertEqual(self.client.post(url, {"confirm": "CANCEL SANDBOX ORDER"}).status_code, 202)
        client_class.return_value.cancel_order.assert_called_once_with(str(self.account_id), str(order_id))
