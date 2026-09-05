from django.contrib import admin

from .models import AnalyticsEvent, Article


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
	list_display = ("title", "slug", "created_at")
	search_fields = ("title", "slug", "content")
	ordering = ("-created_at",)


@admin.register(AnalyticsEvent)
class AnalyticsEventAdmin(admin.ModelAdmin):
	list_display = ("occurred_at", "event_name", "path", "device_type", "referrer_host")
	list_filter = ("event_name", "device_type", "occurred_at")
	search_fields = ("path", "referrer_host", "visitor_hash")
	readonly_fields = ("occurred_at",)
	ordering = ("-occurred_at",)
