from django.core.cache import cache
from .models import StockScore
from .scoring import blended_score

CACHE_TTL = 60 * 15  # 15 minutes

def compute_and_store(symbol: str, tech_weight=0.5, fund_weight=0.5, extra=None):
    ta_weights = (extra or {}).get("ta_weights")
    cache_key = f"ranker:{symbol}:{tech_weight}:{fund_weight}:{ta_weights}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    final, tech, fund, comps = blended_score(
        symbol, tech_weight, fund_weight, ta_weights=ta_weights
    )
    obj, _ = StockScore.objects.update_or_create(
        symbol=symbol.upper(),
        defaults={
            "tech_score": tech,
            "fundamental_score": fund,
            "final_score": final,
            "components": comps,
        },
    )
    cache.set(cache_key, obj, CACHE_TTL)
    return obj

def rank_symbols(symbols, tech_weight=0.5, fund_weight=0.5, extra=None):
    results, errors = [], []
    for s in symbols:
        try:
            obj = compute_and_store(s, tech_weight, fund_weight, extra=extra)
            results.append(obj)
        except Exception as e:
            errors.append({"symbol": s, "error": str(e)})
    results.sort(key=lambda x: x.final_score, reverse=True)
    return results, errors
