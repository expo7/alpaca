from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Article


@override_settings(QUANTELLE_RESEARCH_OPERATOR_TOKEN="x" * 40)
class OperatorArticlePublicationTests(TestCase):
    def setUp(self):
        self.url = reverse("operator-article-publication")
        self.payload = {
            "title": "How to Read a Paper Options Trade Record",
            "slug": "how-to-read-a-paper-options-trade-record",
            "content": "An educational article about paper options outcomes and risks.",
        }

    def test_requires_operator_token_and_is_idempotent(self):
        self.assertNotEqual(self.client.post(self.url, self.payload).status_code, 201)
        headers = {"HTTP_AUTHORIZATION": "Bearer " + "x" * 40}
        first = self.client.post(self.url, self.payload, **headers)
        self.assertEqual(first.status_code, 201)
        again = self.client.post(self.url, self.payload, **headers)
        self.assertEqual(again.status_code, 200)
        self.assertTrue(again.json()["already_applied"])
        self.assertEqual(Article.objects.count(), 1)
        changed = {**self.payload, "content": "Different public content with a sufficiently long description."}
        self.assertEqual(self.client.post(self.url, changed, **headers).status_code, 409)
        self.assertEqual(Article.objects.get().content, self.payload["content"])
