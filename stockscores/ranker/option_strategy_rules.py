"""Contract identity, allowed structures and transparent one-unit risk bounds."""
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

KINDS = {"vertical", "iron_condor", "straddle", "strangle", "calendar", "diagonal", "double_diagonal"}


def number(value):
    try:
        v = Decimal(str(value))
        if not v.is_finite():
            raise ValueError("Non-finite price")
        return v
    except (InvalidOperation, TypeError):
        raise ValueError("Invalid numeric value")


def contract(value):
    m = re.fullmatch(r"([A-Z]{1,6})(\d{6})([CP])(\d{8})", str(value))
    if not m:
        raise ValueError("Use an exact standard OCC option symbol")
    root, expiry, kind, strike = m.groups()
    return {"symbol": value, "underlying": root, "expiration": datetime.strptime(expiry, "%y%m%d").date(),
            "type": kind, "strike": Decimal(strike) / 1000}


def validate_structure(kind, legs, entry_limit):
    if kind not in KINDS or not isinstance(legs, list) or len(legs) not in (2, 4):
        raise ValueError("Supported strategies require two or four legs")
    parsed = []
    for leg in legs:
        if not isinstance(leg, dict) or set(leg) != {"symbol", "side"} or leg["side"] not in {"buy", "sell"}:
            raise ValueError("Each leg requires exactly symbol and side; ratio and quantity are one")
        parsed.append(dict(contract(leg["symbol"]), side=leg["side"]))
    if len({l["symbol"] for l in parsed}) != len(parsed) or len({l["underlying"] for l in parsed}) != 1:
        raise ValueError("Legs must be distinct contracts on one underlying")
    expiries = {l["expiration"] for l in parsed}
    buys = [l for l in parsed if l["side"] == "buy"]
    sells = [l for l in parsed if l["side"] == "sell"]
    debit = number(entry_limit)
    if not debit or debit != debit.quantize(Decimal(".01")):
        raise ValueError("Net entry limit must be a nonzero cent price: debit positive, credit negative")
    if kind == "vertical":
        if len(parsed) != 2 or len(expiries) != 1 or len(buys) != 1 or len(sells) != 1 or buys[0]["type"] != sells[0]["type"]:
            raise ValueError("A vertical needs one long and one short of the same type and expiration")
    elif kind == "iron_condor":
        puts = sorted([l for l in parsed if l["type"] == "P"], key=lambda l:l["strike"])
        calls = sorted([l for l in parsed if l["type"] == "C"], key=lambda l:l["strike"])
        if (len(parsed) != 4 or len(expiries) != 1 or len(puts) != 2 or len(calls) != 2
                or [l["side"] for l in puts + calls] != ["buy", "sell", "sell", "buy"]
                or puts[1]["strike"] >= calls[0]["strike"] or debit >= 0):
            raise ValueError("Credit iron condor needs ordered long put/short put/short call/long call")
    elif kind in {"straddle", "strangle"}:
        if len(parsed) != 2 or sells or len(expiries) != 1 or {l["type"] for l in buys} != {"C", "P"} or debit <= 0:
            raise ValueError("Only long, same-expiration straddles/strangles are supported")
        call = next(l for l in buys if l["type"] == "C")
        put = next(l for l in buys if l["type"] == "P")
        if (kind == "straddle" and call["strike"] != put["strike"]) or (kind == "strangle" and call["strike"] <= put["strike"]):
            raise ValueError("Straddle strikes must match; a strangle's put strike must be below its call")
    else:
        expected = 4 if kind == "double_diagonal" else 2
        if len(parsed) != expected or len(buys) != expected // 2 or len(sells) != expected // 2 or len(expiries) != 2 or debit <= 0:
            raise ValueError("Time spreads need a later long and earlier short for each option type, for a debit")
        if len({l["expiration"] for l in buys}) != 1 or len({l["expiration"] for l in sells}) != 1 or buys[0]["expiration"] <= sells[0]["expiration"]:
            raise ValueError("Every long must expire after every short")
        types = {"C", "P"} if kind == "double_diagonal" else {parsed[0]["type"]}
        if any(sum(l["type"] == t for l in buys) != 1 or sum(l["type"] == t for l in sells) != 1 for t in types):
            raise ValueError("Each option type needs exactly one long and one short")
        if kind == "calendar" and buys[0]["strike"] != sells[0]["strike"]:
            raise ValueError("Calendar strikes must match")
        if kind == "double_diagonal" and any(next(l["strike"] for l in group if l["type"] == "P") >= next(l["strike"] for l in group if l["type"] == "C") for group in (buys, sells)):
            raise ValueError("Double-diagonal put strikes must be below call strikes")
        bound = debit + sum(abs(next(l["strike"] for l in buys if l["type"] == t) - next(l["strike"] for l in sells if l["type"] == t)) for t in types)
        return parsed, {"max_loss_dollars": str(bound * 100), "max_profit_dollars": None,
                        "basis": "Conservative premium plus strike-gap bound; not an expiry payoff forecast. Assignment and execution can add losses."}
    strikes = {Decimal(0), *(l["strike"] for l in parsed)}
    def payoff(s):
        return sum((1 if l["side"] == "buy" else -1) * max(Decimal(0), (s - l["strike"]) if l["type"] == "C" else (l["strike"] - s)) for l in parsed) - debit
    values = [payoff(s) for s in strikes]
    slope = sum((1 if l["side"] == "buy" else -1) for l in parsed if l["type"] == "C")
    if slope < 0 or min(values) >= 0:
        raise ValueError("Structure/price is uncovered or implies an invalid guaranteed payoff")
    risk = {"max_loss_dollars": str(-min(values) * 100),
            "max_profit_dollars": None if slope > 0 else str(max(values) * 100),
            "basis": "Theoretical same-expiration payoff, before fees, assignment and execution effects"}
    if risk["max_profit_dollars"] is not None and number(risk["max_profit_dollars"]) <= 0:
        raise ValueError("Entry price exceeds the structure's achievable payoff")
    return parsed, risk


def signed_fill(order, legs):
    """Derive signed cashflows from observed fills, never the parent mark."""
    if order.get("status") != "filled":
        raise ValueError("Order has not filled")
    observed = {l.get("symbol"): l for l in order.get("legs", [])}
    if set(observed) != {l["symbol"] for l in legs}:
        raise ValueError("Broker fill legs do not match the strategy")
    total = Decimal(0)
    for leg in legs:
        fill = observed[leg["symbol"]]
        price = number(fill.get("filled_avg_price"))
        if number(fill.get("filled_qty")) != 1 or price < 0:
            raise ValueError("Expected one observed fill on every leg")
        total += price if leg["side"] == "buy" else -price
    return total
