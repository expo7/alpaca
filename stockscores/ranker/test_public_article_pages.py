import tempfile
from pathlib import Path

from django.test import TestCase, override_settings

from .models import Article
from .public_article_pages import write_public_article_pages


class PublicArticlePagesTests(TestCase):
    def test_article_html_is_crawlable_escaped_and_current(self):
        with tempfile.TemporaryDirectory() as directory, override_settings(QUANTELLE_FRONTEND_DIST=directory):
            dist = Path(directory)
            (dist / "index.html").write_text(
                '<html><head><meta name="description" content="generic" />'
                '<title>Generic</title></head><body><div id="root"><main>Generic</main></div>'
                '<script src="/assets/app.js"></script></body></html>', encoding="utf-8",
            )
            article = Article.objects.create(title='Market <Notes>', slug="market-notes", content="## Thesis\n\nA & B <script>alert(1)</script>")
            self.assertEqual(write_public_article_pages(), 1)
            page = (dist / "articles" / article.slug).read_text(encoding="utf-8")
            self.assertIn("Market &lt;Notes&gt; | Quantelle", page)
            self.assertIn("A &amp; B alert(1)", page)
            self.assertNotIn("<script>alert(1)</script>", page)
            self.assertIn('href="https://quantelle.io/articles/market-notes"', page)
            self.assertIn('/assets/app.js', page)
            self.assertIn('href="/articles/market-notes"', (dist / "articles" / "index.html").read_text())
            article.delete()
            write_public_article_pages()
            self.assertFalse((dist / "articles" / article.slug).exists())
