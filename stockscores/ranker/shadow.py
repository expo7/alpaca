"""Private prospective shadow research. No broker order path exists here."""

from datetime import timedelta
from decimal import Decimal
import re

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from .models import ResearchRun, ShadowEvent, ShadowSetup, TradeSignal


OCC = re.compile(r"^([A-Z]{1,6})(\d{2})(\d{2})(\d{2})([CP])(\d{8})$")


class ShadowProposalSerializer(serializers.Serializer):
    request_id = serializers.RegexField(r"^github-issue-[1-9][0-9]{0,11}-shadow-[1-9][0-9]?$", max_length=80)
    research_run_id = serializers.IntegerField(min_value=1)
    category = serializers.ChoiceField(choices=ShadowSetup.CATEGORY_CHOICES)
    rejection_reason = serializers.ChoiceField(choices=ShadowSetup.REJECTION_CHOICES, required=False, allow_blank=True)
    benchmark_rationale = serializers.CharField(max_length=500, required=False, allow_blank=True)
    decided_at = serializers.DateTimeField()
    symbol = serializers.RegexField(r"^[A-Z]{1,6}$")
    direction = serializers.ChoiceField(choices=("bullish", "bearish"))
    option_symbol = serializers.CharField(max_length=21)
    expiration = serializers.DateField()
    strike = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal("0.001"))
    option_type = serializers.ChoiceField(choices=("call", "put"))
    contract_multiplier = serializers.IntegerField(min_value=100, max_value=100)
    quantity = serializers.IntegerField(min_value=1, max_value=1)
    underlying_price = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    bid = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    ask = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    midpoint = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal("0.001"))
    quote_at = serializers.DateTimeField()
    spread_dollars = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0"))
    spread_pct = serializers.DecimalField(max_digits=8, decimal_places=2, min_value=Decimal("0"))
    volume = serializers.IntegerField(min_value=0)
    open_interest = serializers.IntegerField(min_value=0)
    entry_trigger = serializers.CharField(min_length=10, max_length=300)
    required_confirmation = serializers.CharField(min_length=10, max_length=300)
    trigger_direction = serializers.ChoiceField(choices=("above", "below"))
    underlying_trigger_price = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    confirmation_seconds = serializers.IntegerField(min_value=60, max_value=1800)
    entry_low = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    entry_high = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    do_not_chase = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    entry_deadline = serializers.DateTimeField()
    stop = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    target_1 = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    target_2 = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    underlying_invalidation = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    expected_reward_risk = serializers.DecimalField(max_digits=8, decimal_places=2, min_value=Decimal("0.01"))
    market_regime = serializers.CharField(min_length=3, max_length=80)
    thesis = serializers.CharField(min_length=20, max_length=2000)
    evidence = serializers.ListField(child=serializers.CharField(max_length=300), min_length=1, max_length=20)
    data_provenance = serializers.CharField(min_length=10, max_length=500)
    ruleset_version = serializers.RegexField(r"^[A-Za-z0-9._-]{1,32}$")
    broker_execution_intended = serializers.BooleanField()

    def validate(self, data):
        now = timezone.now()
        for field in ("decided_at", "quote_at", "entry_deadline"):
            if not isinstance(self.initial_data.get(field), str) or not re.search(r"(Z|[+-]\d\d:\d\d)$", self.initial_data[field]):
                raise serializers.ValidationError({field: "Explicit ISO timezone required."})
        run = ResearchRun.objects.filter(pk=data["research_run_id"], completed_at__isnull=False).first()
        if not run or not run.started_at or run.session_type != "regular":
            raise serializers.ValidationError({"research_run_id": "Completed regular-session research run required."})
        if not (run.started_at <= data["decided_at"] <= run.completed_at <= now and
                now - data["decided_at"] <= timedelta(minutes=10)):
            raise serializers.ValidationError({"decided_at": "Decision must fall within the completed run and reach the operator within ten minutes."})
        if abs((data["decided_at"] - data["quote_at"]).total_seconds()) > 30:
            raise serializers.ValidationError({"quote_at": "Decision quote must be within 30 seconds."})
        if not max(data["decided_at"], now) < data["entry_deadline"] <= data["decided_at"] + timedelta(days=7):
            raise serializers.ValidationError({"entry_deadline": "Future deadline within seven days required."})
        dte = (data["expiration"] - data["decided_at"].date()).days
        if not 21 <= dte <= 60:
            raise serializers.ValidationError({"expiration": "The shadow swing framework requires 21–60 DTE."})
        match = OCC.fullmatch(data["option_symbol"])
        if not match:
            raise serializers.ValidationError({"option_symbol": "Exact OCC option symbol required."})
        year, month, day = (int(v) for v in match.group(2, 3, 4))
        if (match.group(1) != data["symbol"] or
                (2000 + year, month, day) != (data["expiration"].year, data["expiration"].month, data["expiration"].day) or
                match.group(5) != ("C" if data["option_type"] == "call" else "P") or
                Decimal(match.group(6)) / 1000 != data["strike"]):
            raise serializers.ValidationError({"option_symbol": "Contract fields do not match OCC symbol."})
        if data["category"] == "index":
            if data["symbol"] not in ("SPY", "QQQ", "IWM") or not data.get("benchmark_rationale"):
                raise serializers.ValidationError({"category": "Index requires SPY/QQQ/IWM and a rationale."})
        elif not data.get("rejection_reason"):
            raise serializers.ValidationError({"rejection_reason": "Near misses require a structured reason."})
        if (data["direction"], data["option_type"], data["trigger_direction"]) not in (
            ("bullish", "call", "above"), ("bearish", "put", "below"),
        ):
            raise serializers.ValidationError({"direction": "Long call/above or long put/below required."})
        bid, ask = data["bid"], data["ask"]
        midpoint = (bid + ask) / 2
        if ask < bid or abs(data["midpoint"] - midpoint) > Decimal("0.001") or data["spread_dollars"] != ask - bid or abs(data["spread_pct"] - (ask - bid) / midpoint * 100) > Decimal("0.02"):
            raise serializers.ValidationError({"spread_pct": "Quote arithmetic is inconsistent."})
        if not (data["stop"] < data["entry_low"] <= data["entry_high"] <= data["do_not_chase"] < data["target_1"]):
            raise serializers.ValidationError({"entry_high": "Long option stop, entry, chase and target must be ordered."})
        ratio = (data["target_1"] - data["entry_high"]) / (data["entry_high"] - data["stop"])
        if abs(ratio - data["expected_reward_risk"]) > Decimal("0.02"):
            raise serializers.ValidationError({"expected_reward_risk": "Use target 1 and the conservative top of the entry range."})
        if TradeSignal.objects.filter(symbol=data["symbol"], expiration=data["expiration"], strike=data["strike"], instrument_type=data["option_type"], status__in=("published", "open")).exists():
            raise serializers.ValidationError({"option_symbol": "A published active setup already uses this contract."})
        data["research_run"] = run
        return data


def propose(data):
    """Atomic idempotent proposal; broker intent is metadata, never permission."""
    snapshot = {key: str(value) if isinstance(value, Decimal) else value.isoformat() if hasattr(value, "isoformat") else value
                for key, value in data.items() if key not in ("research_run", "research_run_id", "request_id")}
    key = data["request_id"]
    with transaction.atomic():
        existing = ShadowSetup.objects.select_for_update().filter(request_id=key).first()
        if existing:
            if existing.decision != snapshot:
                raise ValueError("Conflicting idempotency replay")
            return existing, True
        if ShadowSetup.objects.filter(decision__option_symbol=data["option_symbol"], status__in=("proposed", "waiting", "active")).exists():
            raise ValueError("An active shadow already uses this contract")
        setup = ShadowSetup.objects.create(
            research_run=data["research_run"], request_id=key, decision=snapshot,
            contract_symbol=data["option_symbol"],
            category=data["category"], rejection_reason=data.get("rejection_reason", ""),
            execution_mode="broker_intended" if data["broker_execution_intended"] else "observation",
            ruleset_version=data["ruleset_version"], decided_at=data["decided_at"],
        )
        ShadowEvent.objects.create(setup=setup, kind="proposed", occurred_at=timezone.now())
        return setup, False


class ShadowObservationSerializer(serializers.Serializer):
    observation_id = serializers.RegexField(r"^[A-Za-z0-9._:-]{8,80}$")
    observed_at = serializers.DateTimeField()
    quote_at = serializers.DateTimeField()
    underlying_price = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    bid = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    ask = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    confirmation_met = serializers.BooleanField()
    thesis_valid = serializers.BooleanField()
    qualitative_thesis_reviewed = serializers.BooleanField(default=False)
    source = serializers.CharField(min_length=10, max_length=300)

    def validate(self, data):
        for field in ("observed_at", "quote_at"):
            raw = self.initial_data.get(field)
            if not isinstance(raw, str) or not re.search(r"(Z|[+-]\d\d:\d\d)$", raw):
                raise serializers.ValidationError({field: "Explicit ISO timezone required."})
        if data["ask"] < data["bid"]:
            raise serializers.ValidationError({"ask": "Crossed quote."})
        now = timezone.now()
        if not now - timedelta(seconds=30) <= data["observed_at"] <= now + timedelta(seconds=2) or abs((data["observed_at"] - data["quote_at"]).total_seconds()) > 30:
            raise serializers.ValidationError({"quote_at": "Future or stale observation/quote."})
        return data


def observe(setup_id, data):
    """Conservative, sampled observation model v1; never makes a broker request."""
    with transaction.atomic():
        setup = ShadowSetup.objects.select_for_update().get(pk=setup_id)
        prior = setup.events.filter(kind="observation", details__observation_id=data["observation_id"]).first()
        payload = {k: str(v) if isinstance(v, Decimal) else v.isoformat() if hasattr(v, "isoformat") else v for k, v in data.items()}
        if prior:
            if prior.details != payload:
                raise ValueError("Conflicting observation replay")
            return setup, True
        if setup.execution_mode != "observation":
            raise ValueError("Observation model cannot settle broker-intended setups")
        if data["observed_at"] < setup.decided_at:
            raise ValueError("Observation predates decision")
        last = setup.events.order_by("-occurred_at", "-id").first()
        if last and data["observed_at"] <= last.occurred_at:
            raise ValueError("Out-of-order observation")
        if setup.status in ("completed", "expired_unfilled", "cancelled", "rejected", "failed"):
            raise ValueError("Setup is terminal")
        d = setup.decision
        bid, ask = data["bid"], data["ask"]
        at = data["observed_at"]
        deadline = timezone.datetime.fromisoformat(d["entry_deadline"])
        if setup.status in ("proposed", "waiting"):
            if at > deadline:
                setup.status = "expired_unfilled"
                ShadowEvent.objects.create(setup=setup, kind="expired_unfilled", occurred_at=at)
            else:
                direction = d["direction"]
                underlying = data["underlying_price"]
                invalidation = Decimal(d["underlying_invalidation"])
                chase = Decimal(d["do_not_chase"])
                trigger = (underlying > invalidation if direction == "bullish" else underlying < invalidation)
                modeled_entry = ask + Decimal("0.01")
                liquid_enough = int(d["volume"]) > 0 and int(d["open_interest"]) > 0 and (ask - bid) / ((ask + bid) / 2) * 100 <= 20
                if (data["confirmation_met"] and data["thesis_valid"] and trigger and liquid_enough and
                        Decimal(d["entry_low"]) <= modeled_entry <= Decimal(d["entry_high"]) and modeled_entry <= chase and
                        at <= timezone.datetime.fromisoformat(d["expiration"] + "T23:59:59+00:00")):
                    # A sampled ask at the evaluation moment is a modeled fill, never a midpoint.
                    setup.status = "active"
                    setup.activated_at = at
                    setup.entered_at = at
                    setup.result = {"fill_model": "sampled-ask-bid-v1", "modeled_entry": str(modeled_entry),
                                    "time_to_entry_seconds": (at - setup.decided_at).total_seconds(),
                                    "mfe_pct": "0", "mae_pct": "0", "thesis_valid": True if data["qualitative_thesis_reviewed"] else None,
                                    "price_level_valid": True,
                                    "confidence": "low", "result_type": "modeled"}
                    ShadowEvent.objects.create(setup=setup, kind="modeled_entry", occurred_at=at,
                                               details={"price": str(modeled_entry), "source": data["source"]})
                else:
                    setup.status = "waiting"
        elif setup.status == "active":
            result = setup.result.copy()
            entry = Decimal(result["modeled_entry"])
            modeled_exit = max(Decimal("0"), bid - Decimal("0.01"))
            excursion = (modeled_exit - entry) / entry * 100
            result["mfe_pct"] = str(max(Decimal(result["mfe_pct"]), excursion))
            result["mae_pct"] = str(min(Decimal(result["mae_pct"]), excursion))
            result["unrealized_return_pct"] = str(excursion)
            result["price_level_valid"] = bool(data["thesis_valid"])
            if data["qualitative_thesis_reviewed"]:
                result["thesis_valid"] = bool(data["thesis_valid"])
            if bid <= Decimal(d["stop"]) or bid >= Decimal(d["target_1"]):
                reason = "stopped" if bid <= Decimal(d["stop"]) else "targeted"
                # A gap exits at the observed bid; never substitute the planned stop/target.
                result["modeled_exit"] = str(modeled_exit)
                result["exit_reason"] = reason
                result["realized_return_dollars"] = str((modeled_exit - entry) * Decimal(d["contract_multiplier"]))
                result["realized_return_pct"] = str(excursion)
                result["time_to_" + ("stop" if reason == "stopped" else "target") + "_seconds"] = (at - setup.entered_at).total_seconds()
                result.pop("unrealized_return_pct", None)
                setup.exited_at = at
                setup.status = "completed"
                ShadowEvent.objects.create(setup=setup, kind=reason, occurred_at=at,
                                           details={"price": str(modeled_exit), "source": data["source"]})
            setup.result = result
        ShadowEvent.objects.create(setup=setup, kind="observation", occurred_at=at, details=payload)
        setup.save()
        return setup, False
