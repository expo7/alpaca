// BacktestChart expects priceData items with fields: timestamp (string), barIndex (number), close, optional sma20/sma50/rsi/macd/macdSignal/macdHist, and buyPrice/sellPrice for markers; equityData items with timestamp, barIndex, equity.
import {
  ComposedChart,
  LineChart,
  Line,
  Scatter,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";

export default function BacktestChart({ priceData = [], equityData = [], rsiBuyLevel, rsiSellLevel }) {
  if (!priceData || priceData.length === 0) {
    return <div className="text-xs text-slate-500">No chart data.</div>;
  }

  const syncId = "backtest";
  const hasRSI = priceData.some((d) => d.rsi != null);
  const hasMACD = priceData.some((d) => d.macd != null || d.macdSignal != null || d.macdHist != null);
  const buyDates = priceData.filter((d) => d.buyPrice != null).map((d) => d.timestamp);
  const sellDates = priceData.filter((d) => d.sellPrice != null).map((d) => d.timestamp);

  return (
    <div
      className="w-full"
      style={{ width: "100%", height: 650, display: "flex", flexDirection: "column", gap: 8, minWidth: 0 }}
    >
      {/* Price + orders + indicators */}
      <div style={{ width: "100%", flex: 3, minHeight: 320, minWidth: 0 }}>
        <ResponsiveContainer width="100%" height="100%" minWidth={200} minHeight={240}>
          <ComposedChart
            data={priceData}
            syncId={syncId}
            margin={{ top: 10, right: 40, bottom: 0, left: 0 }}
          >
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="timestamp" minTickGap={24} />
            <YAxis yAxisId="price" domain={["auto", "auto"]} />
            <Tooltip />
            <Legend layout="vertical" align="right" verticalAlign="middle" />

            <Line
              yAxisId="price"
              type="monotone"
              dataKey="close"
              dot={false}
              isAnimationActive={false}
              name="Price"
              stroke="#a78bfa"
            />

            {priceData.some((d) => d.sma20 != null) && (
              <Line
                yAxisId="price"
                type="monotone"
                dataKey="sma20"
                dot={false}
                isAnimationActive={false}
                strokeDasharray="4 2"
                name="SMA 20"
                stroke="#22c55e"
              />
            )}
            {priceData.some((d) => d.sma50 != null) && (
              <Line
                yAxisId="price"
                type="monotone"
                dataKey="sma50"
                dot={false}
                isAnimationActive={false}
                strokeDasharray="5 3"
                name="SMA 50"
                stroke="#f97316"
              />
            )}

            {priceData.some((d) => d.buyPrice != null) && (
              <Scatter
                yAxisId="price"
                dataKey="buyPrice"
                name="Buys"
                fill="#22c55e"
                shape="triangle"
                isAnimationActive={false}
              />
            )}
            {priceData.some((d) => d.sellPrice != null) && (
              <Scatter
                yAxisId="price"
                dataKey="sellPrice"
                name="Sells"
                fill="#f87171"
                shape="triangleDown"
                isAnimationActive={false}
              />
            )}

            {priceData.some((d) => d.volume != null) && (
              <>
                <YAxis yAxisId="volume" orientation="right" domain={[0, "auto"]} hide />
                <Bar yAxisId="volume" dataKey="volume" name="Volume" fill="#64748b" opacity={0.3} />
              </>
            )}
            {buyDates.map((x) => (
              <ReferenceLine key={`buy-${x}`} x={x} stroke="#22c55e" strokeOpacity={0.4} />
            ))}
            {sellDates.map((x) => (
              <ReferenceLine key={`sell-${x}`} x={x} stroke="#f87171" strokeOpacity={0.4} />
            ))}
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Oscillator panel */}
      {(hasRSI || hasMACD) && (
        <div style={{ width: "100%", flex: 1, minHeight: 140, minWidth: 0 }}>
          <ResponsiveContainer width="100%" height="100%" minWidth={200} minHeight={140}>
            <LineChart data={priceData} syncId={syncId} margin={{ top: 0, right: 40, bottom: 0, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="timestamp" minTickGap={24} />
              <YAxis
                yAxisId="osc"
                domain={hasRSI ? [0, 100] : ["auto", "auto"]}
                allowDecimals={!hasRSI}
              />
              <Tooltip />
              <Legend layout="vertical" align="right" verticalAlign="middle" />

              {hasRSI && (
                <Line
                  yAxisId="osc"
                  type="monotone"
                  dataKey="rsi"
                  dot={false}
                  isAnimationActive={false}
                  name="RSI"
                  stroke="#38bdf8"
                />
              )}

              {typeof rsiBuyLevel === "number" && (
                <ReferenceLine
                  yAxisId="osc"
                  y={rsiBuyLevel}
                  strokeDasharray="3 3"
                  stroke="#22c55e"
                  label={{ value: "RSI Buy", position: "insideLeft", fontSize: 10, fill: "#22c55e" }}
                />
              )}
              {typeof rsiSellLevel === "number" && (
                <ReferenceLine
                  yAxisId="osc"
                  y={rsiSellLevel}
                  strokeDasharray="3 3"
                  stroke="#f97316"
                  label={{ value: "RSI Sell", position: "insideLeft", fontSize: 10, fill: "#f97316" }}
                />
              )}

              {hasMACD && (
                <>
                  <Line
                    yAxisId="osc"
                    type="monotone"
                    dataKey="macd"
                    dot={false}
                    isAnimationActive={false}
                    name="MACD"
                    stroke="#e879f9"
                  />
                  <Line
                    yAxisId="osc"
                    type="monotone"
                    dataKey="macdSignal"
                    dot={false}
                    isAnimationActive={false}
                    name="Signal"
                    stroke="#fbbf24"
                  />
                  {priceData.some((d) => d.macdHist != null) && (
                    <Bar yAxisId="osc" dataKey="macdHist" name="Hist" fill="#94a3b8" opacity={0.6} />
                  )}
                </>
              )}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Equity panel */}
      {equityData && equityData.length > 0 && (
        <div style={{ width: "100%", flex: 1, minHeight: 140, minWidth: 0 }}>
          <ResponsiveContainer width="100%" height="100%" minWidth={200} minHeight={140}>
            <LineChart data={equityData} syncId={syncId} margin={{ top: 0, right: 40, bottom: 16, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="timestamp" minTickGap={24} />
              <YAxis domain={["auto", "auto"]} />
              <Tooltip />
              <Legend layout="vertical" align="right" verticalAlign="middle" />
              <Line
                type="monotone"
                dataKey="equity"
                dot={false}
                isAnimationActive={false}
                name="Equity"
                stroke="#a78bfa"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
