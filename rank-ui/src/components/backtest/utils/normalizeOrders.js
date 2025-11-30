export function normalizeOrders(rawTrades = [], candles = []) {
  const rows = [];
  // helper to find nearest candle by date/ts
  const nearestBar = (tsVal) => {
    if (tsVal == null || !candles.length) return undefined;
    let best = undefined;
    let bestDiff = Infinity;
    candles.forEach((c) => {
      const diff = Math.abs((c.ts ?? 0) - tsVal);
      if (diff < bestDiff) {
        bestDiff = diff;
        best = c.barIndex;
      }
    });
    return best;
  };

  (rawTrades || []).forEach((t, idx) => {
    const entryDateStr = (t.entry_time || t.timestamp || t.time || "").slice(0, 10);
    const exitDateStr = (t.exit_time || "").slice(0, 10);
    const entryTs = entryDateStr ? new Date(entryDateStr).getTime() : null;
    const exitTs = exitDateStr ? new Date(exitDateStr).getTime() : null;

    if (entryTs != null) {
      rows.push({
        id: `${t.symbol || "trade"}-${idx}-entry`,
        symbol: t.symbol || "",
        side: "buy",
        ts: entryTs,
        date: entryDateStr,
        barIndex: nearestBar(entryTs),
        price:
          t.entry_price != null
            ? Number(t.entry_price)
            : t.price != null
            ? Number(t.price)
            : t.fill_price != null
            ? Number(t.fill_price)
            : null,
        qty: t.qty ?? t.quantity ?? null,
      });
    }

    if (exitTs != null) {
      rows.push({
        id: `${t.symbol || "trade"}-${idx}-exit`,
        symbol: t.symbol || "",
        side: "sell",
        ts: exitTs,
        date: exitDateStr,
        barIndex: nearestBar(exitTs),
        price: t.exit_price != null ? Number(t.exit_price) : null,
        qty: t.qty ?? t.quantity ?? null,
      });
    }
  });
  return rows.filter((o) => Number.isFinite(o.ts) && Number.isFinite(o.price)).sort((a, b) => a.ts - b.ts);
}

export default normalizeOrders;
