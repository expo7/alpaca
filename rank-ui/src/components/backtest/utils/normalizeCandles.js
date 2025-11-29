export function normalizeCandles(raw = []) {
  return (raw || [])
    .map((c, idx) => {
      const date = c.date || c.timestamp || c.time || c.t || "";
      const ts = date ? new Date(date).getTime() : idx;
      return {
        date: typeof date === "string" ? date.slice(0, 10) : date,
        ts,
        open: Number(c.open ?? c.o ?? c.Open ?? 0),
        high: Number(c.high ?? c.h ?? c.High ?? 0),
        low: Number(c.low ?? c.l ?? c.Low ?? 0),
        close: Number(c.close ?? c.c ?? c.Close ?? 0),
        volume: c.volume ?? c.v ?? null,
        sma_fast: c.sma_fast ?? null,
        sma_slow: c.sma_slow ?? null,
        rsi: c.rsi ?? null,
        macd: c.macd ?? null,
        macd_signal: c.macd_signal ?? null,
      };
    })
    .filter((c) => Number.isFinite(c.ts) && Number.isFinite(c.close))
    .sort((a, b) => a.ts - b.ts);
}

export default normalizeCandles;
