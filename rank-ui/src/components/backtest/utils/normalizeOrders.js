export function normalizeOrders(rawTrades = []) {
  const rows = [];
  (rawTrades || []).forEach((t, idx) => {
    const entryDate = (t.entry_time || t.timestamp || t.time || "").slice(0, 19);
    const exitDate = (t.exit_time || "").slice(0, 19);
    const entryTs = entryDate ? new Date(entryDate).getTime() : null;
    const exitTs = exitDate ? new Date(exitDate).getTime() : null;

    if (entryTs != null) {
      rows.push({
        id: `${t.symbol || "trade"}-${idx}-entry`,
        symbol: t.symbol || "",
        side: "buy",
        ts: entryTs,
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
        price: t.exit_price != null ? Number(t.exit_price) : null,
        qty: t.qty ?? t.quantity ?? null,
      });
    }
  });
  return rows.filter((o) => Number.isFinite(o.ts) && Number.isFinite(o.price)).sort((a, b) => a.ts - b.ts);
}

export default normalizeOrders;
