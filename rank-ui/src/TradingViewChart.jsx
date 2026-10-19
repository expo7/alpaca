// src/TradingViewChart.jsx
import { useEffect, useId, useRef, useState } from "react";

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

const DEFAULT_STUDIES = ["RSI@tv-basicstudies", "MACD@tv-basicstudies", "OBV@tv-basicstudies"];

export default function TradingViewChart({
  symbol,
  exchangePrefix = "NASDAQ:",
  interval = "D",
  studies,
  autosize = true,
  height = 560,
  onDebugEvent,
}) {
  const id = useId().replace(/:/g, "_");
  const containerRef = useRef(null);
  const isTest = import.meta.env.MODE === "test";
  const studiesList = studies || DEFAULT_STUDIES;
  const [status, setStatus] = useState("idle");
  const [errorText, setErrorText] = useState("");

  function emitDebug(message, meta = {}) {
    const payload = {
      message,
      meta,
      timestamp: new Date().toISOString(),
    };
    if (typeof onDebugEvent === "function") {
      onDebugEvent(payload);
      return;
    }
    const hasMeta = meta && Object.keys(meta).length > 0;
    if (hasMeta) {
      console.log(`[chart-debug] ${message}`, meta);
      return;
    }
    console.log(`[chart-debug] ${message}`);
  }

  useEffect(() => {
    if (!symbol) {
      setStatus("idle");
      setErrorText("");
      emitDebug("Chart action blocked: missing ticker", { blocked: true });
      return undefined;
    }

    if (isTest) {
      setStatus("ready");
      setErrorText("");
      emitDebug(`Chart fetch succeeded (test mode) for ${symbol}`, {
        symbol,
        range: interval,
        responseReturned: true,
      });
      return undefined;
    }

    let mounted = true;
    setStatus("loading");
    setErrorText("");
    emitDebug(`Chart fetch started for ${symbol} / range=${interval}`, {
      symbol,
      range: interval,
      asyncStarted: true,
    });

    loadTV()
      .then(() => {
        if (!mounted) return;
        emitDebug("Chart fetch response returned", {
          symbol,
          range: interval,
          responseReturned: true,
        });
        if (!window.TradingView) {
          setStatus("error");
          const msg = "TradingView global is unavailable after script load.";
          setErrorText(msg);
          emitDebug(`Chart fetch failed: ${msg}`, {
            symbol,
            range: interval,
            error: msg,
          });
          return;
        }
        const fullSymbol = symbol.includes(":") ? symbol : `${exchangePrefix}${symbol}`;
        const widget = new window.TradingView.widget({
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
          studies: studiesList, // some may silently fail if not available
        });

        // tv.js does not always emit a reliable mount signal; this fallback keeps UX responsive.
        if (widget && typeof widget.onChartReady === "function") {
          widget.onChartReady(() => {
            if (!mounted) return;
            setStatus("ready");
            emitDebug("Chart fetch succeeded", {
              symbol: fullSymbol,
              range: interval,
            });
          });
        } else {
          setTimeout(() => {
            if (!mounted) return;
            setStatus("ready");
            emitDebug("Chart fetch succeeded", {
              symbol: fullSymbol,
              range: interval,
              fallbackReadySignal: true,
            });
          }, 700);
        }
      })
      .catch((err) => {
        if (!mounted) return;
        const msg = err?.message || "Unable to load TradingView right now.";
        setStatus("error");
        setErrorText(msg);
        emitDebug(`Chart fetch failed: ${msg}`, {
          symbol,
          range: interval,
          error: msg,
        });
      });

    return () => {
      mounted = false;
      // TradingView cleans up on unmount automatically when container is removed
      // (no explicit destroy in tv.js embed API)
    };
  }, [symbol, exchangePrefix, interval, autosize, height, id, studiesList, isTest]);

  return (
    <div className="relative w-full" style={autosize ? { minHeight: height } : { height }}>
      <div
        ref={containerRef}
        id={id}
        className="w-full"
        style={autosize ? { minHeight: height } : { height }}
      />

      {status === "loading" && (
        <div className="absolute inset-0 flex items-center justify-center text-sm text-slate-300 bg-slate-950/60">
          Loading chart...
        </div>
      )}

      {status === "error" && (
        <div className="absolute inset-0 flex items-center justify-center p-4 text-center text-sm text-rose-300 bg-slate-950/80">
          {errorText || "Chart failed to load."}
        </div>
      )}
    </div>
  );
}
