// src/TradingViewChart.jsx
import { useEffect, useId, useRef } from "react";

// Load tradingview script once
let tvLoader;
function loadTV() {
  if (!tvLoader) {
    tvLoader = new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = "https://s3.tradingview.com/tv.js";
      s.async = true;
      s.onload = () => resolve();
      s.onerror = (e) => reject(e);
      document.head.appendChild(s);
    });
  }
  return tvLoader;
}

/**
 * Props:
 * - symbol: e.g., "AAPL" (we'll prefix with NASDAQ: by default)
 * - exchangePrefix: e.g., "NASDAQ:" or "NYSE:" (default "NASDAQ:")
 * - interval: "D" | "60" | "240" | etc. (default "D")
 * - studies: array of tv-basicstudies ids (optional)
 */
export default function TradingViewChart({
  symbol,
  exchangePrefix = "NASDAQ:",
  interval = "D",
  studies = ["RSI@tv-basicstudies", "MACD@tv-basicstudies", "OBV@tv-basicstudies"],
  autosize = true,
  height = 560,
}) {
  const id = useId().replace(/:/g, "_");
  const containerRef = useRef(null);

  useEffect(() => {
    let widget;
    let mounted = true;

    loadTV()
      .then(() => {
        if (!mounted || !window.TradingView) return;
        const fullSymbol = symbol.includes(":") ? symbol : `${exchangePrefix}${symbol}`;
        widget = new window.TradingView.widget({
          symbol: fullSymbol,
          interval,
          timezone: "Etc/UTC",
          theme: "dark",
          style: "1",
          locale: "en",
          toolbar_bg: "#0b1220",
          hide_top_toolbar: false,
          hide_legend: false,
          allow_symbol_change: true,
          autosize,
          container_id: id,
          height: autosize ? undefined : height,
          studies, // some may silently fail if not available
        });
      })
      .catch(console.error);

    return () => {
      mounted = false;
      // TradingView cleans up on unmount automatically when container is removed
      // (no explicit destroy in tv.js embed API)
    };
  }, [symbol, exchangePrefix, interval, autosize, height, id, studies]);

  return (
    <div
      ref={containerRef}
      id={id}
      className="w-full"
      style={autosize ? { minHeight: height } : { height }}
    />
  );
}
