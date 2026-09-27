import os
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APITestCase

from .customer_paper import PAPER_ACCOUNT_URL, TOKEN_URL
from .models import CustomerPaperConnection


class CustomerPaperConnectionTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="paper-customer", password="secret")
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        self.client.force_authenticate(self.user)
        cache.clear()

    @patch.dict(os.environ, {"ALPACA_CONNECT_ENABLED": "false"})
    def test_feature_is_unavailable_without_app_approval_and_secrets(self):
        self.assertFalse(self.client.get(reverse("customer-paper-connection")).data["available"])
        self.assertEqual(self.client.post(reverse("customer-paper-connect")).status_code, 503)

    def test_paper_only_oauth_and_one_use_callback_store_encrypted_token(self):
        env = {
            "ALPACA_CONNECT_ENABLED": "true", "ALPACA_CONNECT_CLIENT_ID": "test-client",
            "ALPACA_CONNECT_CLIENT_SECRET": "test-secret",
            "ALPACA_CONNECT_REDIRECT_URI": "https://quantelle.io/api/alpaca-paper/callback/",
            "ALPACA_CONNECT_TOKEN_KEY": Fernet.generate_key().decode(),
        }
        with patch.dict(os.environ, env), patch("ranker.customer_paper.requests.post") as post, patch("ranker.customer_paper.requests.get") as get:
            start = self.client.post(reverse("customer-paper-connect"))
            self.assertEqual(start.status_code, 200)
            query = parse_qs(urlparse(start.data["authorize_url"]).query)
            self.assertEqual(query["env"], ["paper"])
            self.assertNotIn("scope", query)  # Read-only; no order access yet.
            post.return_value = Mock(status_code=200, json=lambda: {"access_token": "paper-token"})
            get.return_value = Mock(status_code=200, json=lambda: {"id": "paper-account-1234"})
            callback = reverse("customer-paper-callback")
            response = self.client.get(callback, {"code": "single-use-code", "state": query["state"][0]})
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, "/signals?alpaca=connected")
            self.assertEqual(post.call_args.args[0], TOKEN_URL)
            self.assertEqual(get.call_args.args[0], PAPER_ACCOUNT_URL)
            self.assertEqual(get.call_args.kwargs["headers"], {"Authorization": "Bearer paper-token"})
            connection = CustomerPaperConnection.objects.get(user=self.user)
            self.assertNotIn("paper-token", connection.encrypted_access_token)
            self.assertEqual(Fernet(env["ALPACA_CONNECT_TOKEN_KEY"].encode()).decrypt(connection.encrypted_access_token.encode()), b"paper-token")
            self.assertFalse(self.client.get(reverse("customer-paper-connection")).data["execution_enabled"])
            self.assertEqual(self.client.get(callback, {"code": "again", "state": query["state"][0]}).url, "/signals?alpaca=connection-failed")
            self.assertEqual(post.call_count, 1)
            self.assertEqual(self.client.delete(reverse("customer-paper-connection")).status_code, 204)
            self.assertFalse(CustomerPaperConnection.objects.filter(user=self.user).exists())

    def test_connection_is_staff_only_even_when_available(self):
        self.user.is_staff = False
        self.user.save(update_fields=["is_staff"])
        for name in ("customer-paper-connection", "customer-paper-connect"):
            method = self.client.get if name == "customer-paper-connection" else self.client.post
            self.assertEqual(method(reverse(name)).status_code, 403)
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        self.assertEqual(self.client.get(reverse("customer-paper-connection")).status_code, 200)

    def test_connection_requires_authentication(self):
        self.client.force_authenticate(user=None)
        self.assertIn(self.client.get(reverse("customer-paper-connection")).status_code, (401, 403))
        self.assertIn(self.client.post(reverse("customer-paper-connect")).status_code, (401, 403))
