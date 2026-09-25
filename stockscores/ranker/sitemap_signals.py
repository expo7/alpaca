"""Refresh the public sitemap after an article is committed or removed."""

from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Article
from .public_sitemap import refresh_after_article_change


@receiver(post_save, sender=Article, dispatch_uid="refresh_sitemap_on_article_save")
@receiver(post_delete, sender=Article, dispatch_uid="refresh_sitemap_on_article_delete")
def refresh_article_sitemap(sender, **kwargs):
    transaction.on_commit(refresh_after_article_change)
