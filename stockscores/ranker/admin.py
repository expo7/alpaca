from django.contrib import admin

from .models import Article


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
	list_display = ("title", "slug", "created_at")
	search_fields = ("title", "slug", "content")
	ordering = ("-created_at",)
