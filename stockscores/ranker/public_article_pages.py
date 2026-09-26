"""Write crawlable article HTML into the frontend directory served by Nginx."""

import html
import logging
import os
import re
import tempfile
from pathlib import Path

from django.conf import settings

from .models import Article


logger = logging.getLogger(__name__)
ORIGIN = "https://quantelle.io"


def frontend_directory():
    return Path(getattr(settings, "QUANTELLE_FRONTEND_DIST", settings.BASE_DIR.parent / "rank-ui" / "dist"))


def _plain_text(markdown):
    without_html = re.sub(r"<[^>]*>", " ", markdown)
    return re.sub(r"\s+", " ", re.sub(r"[\[\]#*`_!>]", " ", without_html)).strip()


def _article_body(markdown):
    # Escaped source text is sufficient for crawlers; React renders the full
    # Markdown for readers. Never insert staff-authored HTML into this shell.
    blocks = re.split(r"\n\s*\n", markdown.strip())
    return "\n".join(
        f"<p>{html.escape(_plain_text(block))}</p>"
        for block in blocks if _plain_text(block)
    )


def _render(shell, title, description, canonical, body):
    escaped_title = html.escape(title)
    escaped_description = html.escape(description, quote=True)
    header = (
        f'<meta name="description" content="{escaped_description}" />'
        f'<link rel="canonical" href="{html.escape(canonical, quote=True)}" />'
    )
    shell = re.sub(r'<meta name="description"[^>]*>', lambda _: header, shell, count=1)
    shell = re.sub(r"<title>.*?</title>", lambda _: f"<title>{escaped_title}</title>", shell, count=1, flags=re.S)
    return re.sub(r'<div id="root">.*?</div>', lambda _: f'<div id="root">{body}</div>', shell, count=1, flags=re.S)


def _atomic_write(path, contents):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, prefix=".article-", delete=False) as output:
            temporary = output.name
            output.write(contents)
            os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def write_public_article_pages():
    dist = frontend_directory()
    shell = (dist / "index.html").read_text(encoding="utf-8")
    articles = list(Article.objects.order_by("-created_at"))
    listing = "\n".join(
        f'<li><a href="/articles/{html.escape(article.slug, quote=True)}">{html.escape(article.title)}</a></li>'
        for article in articles
    )
    listing_body = f'<main><h1>Quantelle research articles</h1><ul>{listing}</ul></main>'
    _atomic_write(dist / "articles" / "index.html", _render(
        shell, "Options Research Articles | Quantelle",
        "Read Quantelle options research articles and paper trade analysis.",
        f"{ORIGIN}/articles", listing_body,
    ))
    for article in articles:
        # Host Nginx resolves exact files before its SPA fallback. An
        # extensionless file serves /articles/<slug> without a server change.
        path = dist / "articles" / article.slug
        description = _plain_text(article.content)[:155]
        body = (
            f'<main><nav><a href="/articles">All articles</a></nav>'
            f'<article><h1>{html.escape(article.title)}</h1>'
            f'<time datetime="{article.created_at.date().isoformat()}">{article.created_at.date().isoformat()}</time>'
            f'{_article_body(article.content)}</article></main>'
        )
        _atomic_write(path, _render(shell, f"{article.title} | Quantelle", description,
                                    f"{ORIGIN}/articles/{article.slug}", body))
    # Remove only pages we generated, never arbitrary files under dist.
    active = {article.slug for article in articles}
    for page in (dist / "articles").iterdir():
        if page.is_file() and page.name not in active and page.name != "index.html":
            if '<link rel="canonical" href="https://quantelle.io/articles/' in page.read_text(encoding="utf-8"):
                page.unlink()
    return len(articles)


def refresh_after_article_change():
    try:
        write_public_article_pages()
    except (OSError, ValueError):
        logger.exception("Could not refresh public article pages after article change")
