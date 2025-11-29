export default function BacktestStatsPanel({ stats }) {
  const rows = [
    { k: "Start equity", v: stats?.start_equity },
    { k: "End equity", v: stats?.end_equity },
    { k: "Total return", v: stats?.return_pct },
    { k: "Max drawdown %", v: stats?.max_drawdown_pct },
    { k: "Trades", v: stats?.num_trades },
    { k: "Win rate %", v: stats?.win_rate_pct },
  ];

  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-4">
      <div className="text-sm font-semibold mb-3">Stats</div>
      <div className="divide-y divide-slate-800 text-sm">
        {rows.map((row) => (
          <div key={row.k} className="flex items-center justify-between py-1.5">
            <span className="text-slate-400">{row.k}</span>
            <span className="text-slate-100">
              {typeof row.v === "number" ? row.v : row.v ?? "-"}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
