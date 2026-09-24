from django.contrib import admin

from .models import AnalyticsEvent, Article, BillingProfile, OperationalTelegramAlert, ResearchRun, TradeExecutorHealth, TradeLifecycleCertification, TradeSignal, TradeSignalUpdate
from .research_runs import run_state


@admin.register(ResearchRun)
class ResearchRunAdmin(admin.ModelAdmin):
	list_display = ("expected_run_at", "session_type", "outcome", "run_status", "candidates_reviewed", "completed_at")
	list_filter = ("outcome", "session_type", "expected_run_at")
	readonly_fields = tuple(field.name for field in ResearchRun._meta.fields)

	@admin.display(description="Health")
	def run_status(self, obj):
		return run_state(obj)

	def has_add_permission(self, request):
		return False

	def has_delete_permission(self, request, obj=None):
		return False


@admin.register(OperationalTelegramAlert)
class OperationalTelegramAlertAdmin(admin.ModelAdmin):
	list_display = ("created_at", "signal", "status", "attempt_count", "sent_at")
	list_filter = ("status", "created_at")
	readonly_fields = ("idempotency_key", "signal", "message", "status", "attempt_count", "last_error", "telegram_message_id", "sent_at", "created_at", "updated_at")

	def has_add_permission(self, request):
		return False

	def has_delete_permission(self, request, obj=None):
		return False
from .trade_quotes import apply_publication_snapshot


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
	list_display = ("display_instrument", "status", "is_test", "risk_level", "entry_low", "target_1", "published_at", "realized_return_pct")
	list_filter = ("status", "is_test", "instrument_type", "risk_level", "published_at")
	search_fields = ("symbol", "company_name", "thesis")
	readonly_fields = (
		"published_at", "created_at", "updated_at", "contract_symbol",
		"publication_underlying_price", "publication_option_bid", "publication_option_ask",
		"publication_option_midpoint", "publication_option_spread_pct", "publication_option_volume", "publication_option_open_interest",
		"publication_quote_at", "publication_quote_source",
		"paper_entry_order_id", "paper_exit_order_id", "paper_order_status",
		"paper_submitted_at", "paper_filled_at", "paper_last_checked_at",
		"paper_last_error", "paper_exit_reason", "trigger_first_seen_at",
	)
	ordering = ("-published_at", "-created_at")
	inlines = (TradeSignalUpdateInline,)
	fieldsets = (
		("Instrument", {"fields": (("symbol", "company_name"), ("instrument_type", "strike", "expiration"), "contract_symbol", ("status", "risk_level"))}),
		("Entry trigger", {"fields": (("trigger_direction", "underlying_trigger_price"), "trigger_confirmation", ("do_not_chase_price", "entry_deadline"), "official_fill_method")}),
		("Trade plan", {"fields": (("entry_low", "entry_high"), ("initial_stop", "current_stop"), ("target_1", "target_2", "target_3"))}),
		("Research", {"fields": ("thesis", "invalidation", "evidence_tags")}),
		("Publication quote snapshot", {
			"fields": (
				("publication_underlying_price", "publication_quote_at"),
				("publication_option_bid", "publication_option_ask", "publication_option_midpoint"),
				("publication_option_spread_pct", "publication_option_volume", "publication_option_open_interest"),
				"publication_quote_source",
			),
			"classes": ("collapse",),
		}),
		("Alpaca paper execution", {
			"fields": (
				("paper_execution_enabled", "paper_quantity", "is_test"),
				("paper_entry_order_id", "paper_exit_order_id", "paper_order_status"),
				("paper_submitted_at", "paper_filled_at", "paper_last_checked_at"),
				("trigger_first_seen_at", "paper_exit_reason"),
				"paper_last_error",
			),
		}),
		("Outcome", {"fields": (("actual_entry", "final_exit"), ("realized_return_pct", "max_return_pct"), ("published_at", "closed_at"))}),
		("Record", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
	)

	def get_readonly_fields(self, request, obj=None):
		base = self.readonly_fields
		if obj and obj.published_at:
			return tuple(dict.fromkeys(base + tuple(
				field for field in TradeSignal.LOCKED_AFTER_PUBLICATION
				if field not in base and getattr(obj, field) not in (None, "", [])
			)))
		return base

	def save_model(self, request, obj, form, change):
		# Capture only on the first publication. Never backfill an old record with a
		# later quote and present it as though it existed at publication time.
		if obj.status != TradeSignal.STATUS_DRAFT and not obj.published_at:
			apply_publication_snapshot(obj)
		super().save_model(request, obj, form, change)


@admin.register(TradeSignalUpdate)
class TradeSignalUpdateAdmin(admin.ModelAdmin):
	list_display = ("occurred_at", "signal", "event_type", "audience", "price", "return_pct")
	list_filter = ("event_type", "audience", "occurred_at")
	search_fields = ("signal__symbol", "note")
	ordering = ("-occurred_at",)

	def has_delete_permission(self, request, obj=None):
		return False

	def get_readonly_fields(self, request, obj=None):
		return () if obj is None else ("signal", "occurred_at", "event_type", "audience", "price", "return_pct", "note")


@admin.register(TradeExecutorHealth)
class TradeExecutorHealthAdmin(admin.ModelAdmin):
	list_display = (
		"status", "entries_paused", "last_started_at", "last_completed_at",
		"last_success_at", "consecutive_failures", "updated_at",
	)
	readonly_fields = (
		"singleton_id", "status", "entries_paused", "last_started_at",
		"last_completed_at", "last_success_at", "degraded_at", "recovered_at",
		"consecutive_failures", "last_error", "updated_at",
	)

	def has_add_permission(self, request):
		return False

	def has_delete_permission(self, request, obj=None):
		return False


@admin.register(TradeLifecycleCertification)
class TradeLifecycleCertificationAdmin(admin.ModelAdmin):
	list_display = ("signal", "status", "lifecycle_certified", "checked_at", "certified_at", "retry_count")
	list_filter = ("status", "lifecycle_certified", "checked_at")
	readonly_fields = ("signal", "status", "lifecycle_certified", "checked_at", "certified_at", "checkpoints", "discrepancy_codes", "discrepancy_details", "retry_count", "created_at", "updated_at")

	def has_add_permission(self, request):
		return False

	def has_delete_permission(self, request, obj=None):
		return False


@admin.register(BillingProfile)
class BillingProfileAdmin(admin.ModelAdmin):
	list_display = ("user", "status", "stripe_customer_id", "current_period_end", "cancel_at_period_end", "updated_at")
	search_fields = ("user__username", "user__email", "stripe_customer_id", "stripe_subscription_id")
	list_filter = ("status", "cancel_at_period_end")
	readonly_fields = (
		"user", "stripe_customer_id", "stripe_subscription_id", "stripe_price_id",
		"status", "current_period_end", "cancel_at_period_end", "updated_at",
	)

	def has_add_permission(self, request):
		return False

	def has_delete_permission(self, request, obj=None):
		return False
