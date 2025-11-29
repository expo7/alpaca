export function mergeOrdersIntoCandles(candles = [], orders = []) {
  if (!candles.length) return [];
  const byTs = new Map();
  candles.forEach((c) => byTs.set(c.ts, { ...c }));

  orders.forEach((o) => {
    const bucket = byTs.get(o.ts);
    if (!bucket) return;
    if (o.side === "buy") {
      bucket.buyPrice = o.price;
    } else if (o.side === "sell") {
      bucket.sellPrice = o.price;
    }
  });

  return Array.from(byTs.values()).sort((a, b) => a.ts - b.ts);
}

export default mergeOrdersIntoCandles;
