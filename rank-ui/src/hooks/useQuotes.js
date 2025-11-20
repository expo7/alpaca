import { useEffect, useState } from "react";

const BASE = "http://127.0.0.1:8000";

// Shared hook to fetch live quotes for a list of symbols with a debounce/poll.
export default function useQuotes(symbols = [], { pollMs = 20000, debounceMs = 400 } = {}) {
  const [quotes, setQuotes] = useState({});

  useEffect(() => {
    if (!symbols.length) return;
    let timeoutId;
    let cancelled = false;

    const fetchQuotes = async () => {
      if (cancelled) return;
      try {
        const res = await fetch(
          `${BASE}/api/paper/quotes/?symbols=${encodeURIComponent(symbols.join(","))}`
        );
        if (!res.ok) return;
        const data = await res.json();
        const priceMap = {};
        (data || []).forEach((q) => {
          priceMap[q.symbol] = q.price;
        });
        if (!cancelled) setQuotes(priceMap);
      } catch {
        // ignore network errors
      }
      if (!cancelled && pollMs > 0) {
        timeoutId = setTimeout(fetchQuotes, pollMs);
      }
    };

    timeoutId = setTimeout(fetchQuotes, debounceMs);
    return () => {
      cancelled = true;
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, [symbols.sort().join(","), pollMs, debounceMs]); // stable key

  return quotes;
}
