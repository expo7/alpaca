from django.contrib import admin

from .models import AnalyticsEvent, Article, TradeSignal, TradeSignalUpdate


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


class TradeSignalUpdateInline(admin.TabularInline):
	model = TradeSignalUpdate
	extra = 0
	fields = ("occurred_at", "event_type", "price", "return_pct", "note")
	ordering = ("occurred_at",)
	can_delete = False

	readonly_fields = ("occurred_at", "event_type", "price", "return_pct", "note")

	def has_add_permission(self, request, obj=None):
		return False


@admin.register(TradeSignal)
class TradeSignalAdmin(admin.ModelAdmin):
	list_display = ("display_instrument", "status", "risk_level", "entry_low", "target_1", "published_at", "realized_return_pct")
	list_filter = ("status", "instrument_type", "risk_level", "published_at")
	search_fields = ("symbol", "company_name", "thesis")
	readonly_fields = ("published_at", "created_at", "updated_at")
	ordering = ("-published_at", "-created_at")
	inlines = (TradeSignalUpdateInline,)
	fieldsets = (
		("Instrument", {"fields": (("symbol", "company_name"), ("instrument_type", "strike", "expiration"), ("status", "risk_level"))}),
		("Trade plan", {"fields": (("entry_low", "entry_high"), ("initial_stop", "current_stop"), ("target_1", "target_2", "target_3"))}),
		("Research", {"fields": ("thesis", "invalidation", "evidence_tags")}),
		("Outcome", {"fields": (("actual_entry", "final_exit"), ("realized_return_pct", "max_return_pct"), ("published_at", "closed_at"))}),
		("Record", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
	)

	def get_readonly_fields(self, request, obj=None):
		base = ("published_at", "created_at", "updated_at")
		if obj and obj.published_at:
			return base + tuple(field for field in TradeSignal.LOCKED_AFTER_PUBLICATION if field != "published_at")
		return base


@admin.register(TradeSignalUpdate)
class TradeSignalUpdateAdmin(admin.ModelAdmin):
	list_display = ("occurred_at", "signal", "event_type", "price", "return_pct")
	list_filter = ("event_type", "occurred_at")
	search_fields = ("signal__symbol", "note")
	ordering = ("-occurred_at",)

	def has_delete_permission(self, request, obj=None):
		return False

	def get_readonly_fields(self, request, obj=None):
		return () if obj is None else ("signal", "occurred_at", "event_type", "price", "return_pct", "note")
