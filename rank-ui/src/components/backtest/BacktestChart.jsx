import { useMemo } from "react";
import { ComposedChart, Line, CartesianGrid, XAxis, YAxis, Tooltip, ResponsiveContainer, Scatter } from "recharts";
import mergeOrdersIntoCandles from "./utils/mergeOrdersIntoCandles.js";

function formatDate(tsOrDate) {
  if (typeof tsOrDate === "string") return tsOrDate.slice(0, 10);
  if (!Number.isFinite(tsOrDate)) return "";
  const d = new Date(tsOrDate);
  if (Number.isNaN(d.getTime())) return "";
  return d.toISOString().slice(0, 10);
}

export default function BacktestChart({ candles = [], orders = [] }) {
  const merged = useMemo(() => mergeOrdersIntoCandles(candles, orders), [candles, orders]);
  if (!merged.length) {
    return <div className="text-xs text-slate-500">No price data yet.</div>;
  }

  return (
    <div className="w-full h-80">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={merged}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" tick={{ fontSize: 10 }} />
          <YAxis tick={{ fontSize: 10 }} domain={["auto", "auto"]} />
          <Tooltip
            formatter={(val, name) => [typeof val === "number" ? val.toFixed(2) : val, name]}
            labelFormatter={(val) => formatDate(val)}
          />
          <Line
            type="monotone"
            dataKey="close"
            name="Close"
            stroke="#a78bfa"
            dot={false}
            isAnimationActive={false}
          />
          {merged.some((d) => d.sma_fast != null) && (
            <Line
              type="monotone"
              dataKey="sma_fast"
              name="SMA Fast"
              stroke="#22c55e"
              dot={false}
              strokeDasharray="4 2"
              isAnimationActive={false}
            />
          )}
          {merged.some((d) => d.sma_slow != null) && (
            <Line
              type="monotone"
              dataKey="sma_slow"
              name="SMA Slow"
              stroke="#f97316"
              dot={false}
              strokeDasharray="3 3"
              isAnimationActive={false}
            />
          )}
          {merged.some((d) => d.buyPrice != null) && (
            <Scatter data={merged.filter((d) => d.buyPrice != null)} name="Buy" dataKey="buyPrice" fill="#22c55e" />
          )}
          {merged.some((d) => d.sellPrice != null) && (
            <Scatter
              data={merged.filter((d) => d.sellPrice != null)}
              name="Sell"
              dataKey="sellPrice"
              fill="#f87171"
              shape="triangleDown"
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
