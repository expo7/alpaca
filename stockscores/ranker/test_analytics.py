from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from .models import AnalyticsEvent


class AnalyticsApiTests(APITestCase):
    def setUp(self):
        self.browser_headers = {
            "HTTP_USER_AGENT": "Mozilla/5.0 Test Browser",
            "REMOTE_ADDR": "203.0.113.10",
        }

    def test_public_event_collection_hashes_visitor_and_strips_referrer_path(self):
        response = self.client.post(
            reverse("analytics-event-create"),
            {
                "event_name": "page_view",
                "path": "/articles/example",
                "referrer": "https://www.google.com/search?q=quantelle",
            },
            format="json",
            **self.browser_headers,
        )

        self.assertEqual(response.status_code, 204)
        event = AnalyticsEvent.objects.get()
        self.assertEqual(event.path, "/articles/example")
        self.assertEqual(event.referrer_host, "www.google.com")
        self.assertEqual(len(event.visitor_hash), 64)
        self.assertNotIn("203.0.113.10", event.visitor_hash)

    def test_known_bot_is_not_recorded(self):
        response = self.client.post(
            reverse("analytics-event-create"),
            {"event_name": "page_view", "path": "/articles/example"},
            format="json",
            HTTP_USER_AGENT="Mozilla/5.0 (compatible; AhrefsBot/7.0)",
            REMOTE_ADDR="203.0.113.11",
        )

        self.assertEqual(response.status_code, 204)
        self.assertFalse(AnalyticsEvent.objects.exists())

    def test_summary_requires_staff_and_aggregates_activity(self):
        User = get_user_model()
        regular_user = User.objects.create_user(username="reader", password="test-pass")
        staff_user = User.objects.create_user(username="owner", password="test-pass", is_staff=True)
        AnalyticsEvent.objects.create(
            event_name="page_view",
            path="/articles/example",
            referrer_host="www.google.com",
            visitor_hash="a" * 64,
            device_type="mobile",
        )
        AnalyticsEvent.objects.create(
            event_name="ranking_run",
            path="/dashboard",
            visitor_hash="a" * 64,
            device_type="mobile",
        )

        self.client.force_authenticate(regular_user)
        self.assertEqual(self.client.get(reverse("analytics-summary")).status_code, 403)

        self.client.force_authenticate(staff_user)
        response = self.client.get(reverse("analytics-summary"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["totals"]["visitors"], 1)
        self.assertEqual(response.data["totals"]["article_views"], 1)
        self.assertEqual(response.data["totals"]["ranking_runs"], 1)
