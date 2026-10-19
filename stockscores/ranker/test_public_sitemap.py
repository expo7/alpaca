from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from xml.etree import ElementTree

from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Article
from .public_sitemap import NS, write_public_sitemap


class PublicSitemapTests(TestCase):
    def urls(self, response):
        root = ElementTree.fromstring(response.content)
        self.assertEqual(root.tag, f"{{{NS}}}urlset")
        return [node.text for node in root.findall(f"{{{NS}}}url/{{{NS}}}loc")]

    def test_public_sitemap_contains_only_real_public_routes_and_articles(self):
        Article.objects.create(title="Published article", slug="published-article", content="Public")
        response = self.client.get(reverse("public-sitemap"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/xml", response["Content-Type"])
        urls = self.urls(response)
        self.assertEqual(len(urls), len(set(urls)))
        for path in ("/", "/signals", "/articles", "/dashboard", "/support", "/privacy", "/terms", "/articles/published-article"):
            self.assertIn(f"https://quantelle.io{path}", urls)
        for path in ("/admin/", "/api/articles/", "/billing", "/analytics", "/opportunities", "/articles/private-draft"):
            self.assertNotIn(f"https://quantelle.io{path}", urls)

    def test_generation_reflects_future_articles_and_deletion(self):
        with TemporaryDirectory() as directory:
            target = Path(directory) / "sitemap.xml"
            write_public_sitemap(target)
            self.assertEqual(len(self.urls(type("Response", (), {"content": target.read_bytes()})())), 7)
            article = Article.objects.create(title="New", slug="new-article", content="Public")
            write_public_sitemap(target)
            self.assertIn("https://quantelle.io/articles/new-article", self.urls(type("Response", (), {"content": target.read_bytes()})()))
            article.delete()
            write_public_sitemap(target)
            self.assertNotIn("https://quantelle.io/articles/new-article", self.urls(type("Response", (), {"content": target.read_bytes()})()))

    def test_article_changes_refresh_sitemap_after_commit(self):
        with patch("ranker.sitemap_signals.refresh_after_article_change") as refresh:
            with self.captureOnCommitCallbacks(execute=True):
                article = Article.objects.create(title="New", slug="new-article", content="Public")
            refresh.assert_called_once()
            refresh.reset_mock()
            with self.captureOnCommitCallbacks(execute=True):
                article.delete()
            refresh.assert_called_once()

    def test_robots_references_sitemap_and_does_not_block_public_pages(self):
        response = self.client.get(reverse("public-robots"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/plain", response["Content-Type"])
        self.assertIn("Sitemap: https://quantelle.io/sitemap.xml", response.content.decode())
        self.assertNotIn("Disallow: /", response.content.decode())
