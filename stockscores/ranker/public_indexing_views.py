from django.conf import settings
from django.http import HttpResponse

from .public_sitemap import render_public_sitemap


def sitemap(request):
    return HttpResponse(render_public_sitemap(), content_type="application/xml")


def robots(request):
    content = (settings.BASE_DIR.parent / "rank-ui" / "public" / "robots.txt").read_text()
    return HttpResponse(content, content_type="text/plain")
