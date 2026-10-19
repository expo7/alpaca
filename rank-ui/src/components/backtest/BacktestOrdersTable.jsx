export default function BacktestOrdersTable({ orders = [] }) {
  if (!orders.length) return null;

  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-4">
      <div className="text-sm font-semibold mb-3">Trades</div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="text-slate-400 border-b border-slate-800">
            <tr className="text-left">
              <th className="py-2 pr-2">Symbol</th>
              <th className="py-2 pr-2">Action</th>
              <th className="py-2 pr-2">Qty</th>
              <th className="py-2 pr-2">Entry</th>
              <th className="py-2 pr-2">Exit</th>
              <th className="py-2 pr-2">Price</th>
              <th className="py-2 pr-2">PnL $</th>
              <th className="py-2 pr-2">PnL %</th>
              <th className="py-2 pr-2">Days held</th>
              <th className="py-2 pr-2">Entry time</th>
              <th className="py-2 pr-2">Exit time</th>
            </tr>
          </thead>
          <tbody>
            {orders.map((t, idx) => (
              <tr
                key={`${t.symbol || "trade"}-${idx}`}
                className="border-t border-slate-900 hover:bg-slate-900/50"
              >
                <td className="py-1.5 pr-2 font-semibold">
                  {t.symbol || "-"}
                </td>
                <td className="py-1.5 pr-2">{t.action || t.side || "-"}</td>
                <td className="py-1.5 pr-2">
                  {t.qty != null
                    ? Number(t.qty).toFixed(2)
                    : t.quantity != null
                    ? Number(t.quantity).toFixed(2)
                    : "-"}
                </td>
                <td className="py-1.5 pr-2">
                  {t.entry_price != null
                    ? Number(t.entry_price).toFixed(2)
                    : t.price != null
                    ? Number(t.price).toFixed(2)
                    : "-"}
                </td>
                <td className="py-1.5 pr-2">
                  {t.exit_price != null ? Number(t.exit_price).toFixed(2) : "-"}
                </td>
                <td className="py-1.5 pr-2">
                  {typeof t.price === "number"
                    ? Number(t.price).toFixed(2)
                    : t.fill_price != null
                    ? Number(t.fill_price).toFixed(2)
                    : "-"}
                </td>
                <td className="py-1.5 pr-2">
                  {t.pnl != null ? Number(t.pnl).toFixed(2) : "-"}
                </td>
                <td className="py-1.5 pr-2">
                  {t.pnl_pct != null ? `${Number(t.pnl_pct).toFixed(2)}%` : "-"}
                </td>
                <td className="py-1.5 pr-2">
                  {t.days_held != null ? Number(t.days_held).toFixed(2) : "-"}
                </td>
                <td className="py-1.5 pr-2">
                  {t.entry_time || t.entry_ts || t.open_time || t.timestamp || t.time || "-"}
                </td>
                <td className="py-1.5 pr-2">
                  {t.exit_time || t.exit_ts || t.close_time || "-"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
