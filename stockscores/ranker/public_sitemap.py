"""Generate the public sitemap served by Nginx from the built frontend directory."""

import logging
import os
import tempfile
from pathlib import Path
from xml.etree import ElementTree

from django.conf import settings

from .models import Article


logger = logging.getLogger(__name__)
NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
ElementTree.register_namespace("", NS)
ORIGIN = "https://quantelle.io"
PUBLIC_PATHS = ("/", "/signals", "/articles", "/dashboard", "/support", "/privacy", "/terms")


def sitemap_output_path():
    return Path(getattr(settings, "QUANTELLE_SITEMAP_PATH", settings.BASE_DIR.parent / "rank-ui" / "dist" / "sitemap.xml"))


def render_public_sitemap():
    root = ElementTree.Element(f"{{{NS}}}urlset")
    paths = list(PUBLIC_PATHS)
    # Articles have no draft/private state: every row is exposed by the public detail API.
    paths.extend(f"/articles/{slug}" for slug in Article.objects.order_by("slug").values_list("slug", flat=True))
    for path in dict.fromkeys(paths):
        url = ElementTree.SubElement(root, f"{{{NS}}}url")
        ElementTree.SubElement(url, f"{{{NS}}}loc").text = f"{ORIGIN}{path}"
    return ElementTree.tostring(root, encoding="utf-8", xml_declaration=True)


def write_public_sitemap(path=None):
    target = Path(path) if path is not None else sitemap_output_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    contents = render_public_sitemap()
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".sitemap-", delete=False) as output:
            temporary = output.name
            output.write(contents)
            os.chmod(temporary, 0o644)
        os.replace(temporary, target)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
    return target


def refresh_after_article_change():
    try:
        write_public_sitemap()
    except OSError:
        logger.exception("Could not refresh public sitemap after article change")
