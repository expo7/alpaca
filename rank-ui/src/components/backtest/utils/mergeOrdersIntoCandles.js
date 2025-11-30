export function mergeOrdersIntoCandles(candles = [], orders = []) {
  if (!candles.length) return [];
  const byIndex = new Map();
  candles.forEach((c) => {
    byIndex.set(c.barIndex, { ...c, buyPrice: null, sellPrice: null });
  });

  orders.forEach((o) => {
    const bucket = byIndex.get(o.barIndex);
    if (!bucket) return;
    if (o.side === "buy") {
      bucket.buyPrice = o.price;
    } else if (o.side === "sell") {
      bucket.sellPrice = o.price;
    }
  });

  return Array.from(byIndex.values()).sort((a, b) => a.barIndex - b.barIndex);
}

export default mergeOrdersIntoCandles;
