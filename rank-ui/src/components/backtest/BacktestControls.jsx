export default function BacktestControls({
  botConfig,
  onUpdateConfig,
  strategyText,
  onStrategyTextChange,
  templates,
  selectedTemplateId,
  onSelectTemplate,
  templateErr,
  validationMsg,
  parseError,
  strategyErrors,
  onValidate,
  onRun,
  isValidating,
  isRunning,
  backtestError,
  chartSymbol,
  onChangeChartSymbol,
  onLoadChart,
  chartLoading,
}) {
  const handleTemplateChange = (id) => {
    onSelectTemplate(id);
  };

  return (
    <div className="sbp-grid two-col">
      <div className="space-y-3">
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-3 space-y-2">
          <div className="flex items-center justify-between">
            <div className="text-sm font-semibold">Templates</div>
            {templateErr && <span className="text-[11px] text-rose-300">{templateErr}</span>}
          </div>
          {templates.map((tpl) => (
            <button
              key={tpl.id}
              type="button"
              onClick={() => handleTemplateChange(tpl.id)}
              className={`w-full text-left px-3 py-2 rounded-xl border transition ${
                selectedTemplateId === tpl.id
                  ? "border-amber-400/70 bg-amber-400/10 text-amber-100"
                  : "border-slate-800 bg-slate-950 hover:border-slate-700 text-slate-200"
              }`}
            >
              <div className="font-semibold text-sm">{tpl.name}</div>
              <div className="text-[11px] text-slate-400">{tpl.description}</div>
            </button>
          ))}
          {!templates.length && !templateErr && (
            <div className="text-xs text-slate-500">Loading templates...</div>
          )}
        </div>

        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-3">
          <div className="flex items-center justify-between mb-2">
            <div>
              <div className="text-sm font-semibold">StrategySpec JSON</div>
              <div className="text-[11px] text-slate-400">
                This is the strategy JSON spec. Edit freely or start from a template above.
              </div>
            </div>
            <button
              type="button"
              onClick={onValidate}
              disabled={isValidating}
              className="btn-primary disabled:opacity-60"
            >
              {isValidating ? "Validating..." : "Validate Strategy"}
            </button>
          </div>

          <textarea
            value={strategyText}
            onChange={(e) => onStrategyTextChange(e.target.value)}
            rows={18}
            className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 font-mono text-xs text-slate-100 focus:border-amber-500 focus:outline-none"
          />

          {parseError && <div className="mt-2 text-xs text-rose-300">JSON parse error: {parseError}</div>}
          {validationMsg && <div className="mt-2 text-xs text-emerald-300">{validationMsg}</div>}
          {strategyErrors && strategyErrors.length > 0 && (
            <div className="mt-2 text-xs text-amber-200 space-y-1">
              {strategyErrors.map((err, idx) => (
                <div key={`${err.field || "err"}-${idx}`}>
                  {err.field ? `${err.field}: ` : ""}
                  {err.message || JSON.stringify(err)}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="space-y-3">
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-4 space-y-3">
          <div className="text-sm font-semibold">Bot config (backtest)</div>
          <div className="space-y-2 text-sm">
            <label className="block">
              <span className="text-xs text-slate-400">Symbols (comma-separated)</span>
              <input
                value={botConfig.symbols}
                onChange={(e) => onUpdateConfig("symbols", e.target.value)}
                className="mt-1 w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm"
                placeholder="AAPL, MSFT, SPY"
              />
            </label>

            <div className="grid grid-cols-2 gap-2">
              <label className="block">
                <span className="text-xs text-slate-400">Start date</span>
                <input
                  type="date"
                  value={botConfig.start_date}
                  onChange={(e) => onUpdateConfig("start_date", e.target.value)}
                  className="mt-1 w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm"
                />
              </label>
              <label className="block">
                <span className="text-xs text-slate-400">End date</span>
                <input
                  type="date"
                  value={botConfig.end_date}
                  onChange={(e) => onUpdateConfig("end_date", e.target.value)}
                  className="mt-1 w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm"
                />
              </label>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <label className="block">
                <span className="text-xs text-slate-400">Rebalance days</span>
                <input
                  type="number"
                  min={1}
                  value={botConfig.rebalance_days}
                  onChange={(e) => onUpdateConfig("rebalance_days", e.target.value)}
                  className="mt-1 w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm"
                  placeholder="5"
                />
              </label>
              <label className="block">
                <span className="text-xs text-slate-400">Top N</span>
                <input
                  type="number"
                  min={1}
                  value={botConfig.top_n ?? ""}
                  onChange={(e) => onUpdateConfig("top_n", e.target.value)}
                  className="mt-1 w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm"
                  placeholder="10"
                />
              </label>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <label className="block">
                <span className="text-xs text-slate-400">Max open positions</span>
                <input
                  type="number"
                  min={1}
                  value={botConfig.max_open_positions ?? ""}
                  onChange={(e) => onUpdateConfig("max_open_positions", e.target.value)}
                  className="mt-1 w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm"
                  placeholder="5"
                />
              </label>
              <label className="block">
                <span className="text-xs text-slate-400">Max per position %</span>
                <input
                  type="number"
                  min={0}
                  max={100}
                  value={botConfig.max_per_position_pct ?? ""}
                  onChange={(e) => onUpdateConfig("max_per_position_pct", e.target.value)}
                  className="mt-1 w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm"
                  placeholder="20"
                />
              </label>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <label className="block">
                <span className="text-xs text-slate-400">Rebalance top N</span>
                <input
                  type="number"
                  min={1}
                  value={botConfig.rebalance_top_n ?? ""}
                  onChange={(e) => onUpdateConfig("rebalance_top_n", e.target.value)}
                  className="mt-1 w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm"
                  placeholder="5"
                />
              </label>
              <label className="block">
                <span className="text-xs text-slate-400">Slippage model</span>
                <select
                  value={botConfig.slippage_model ?? "none"}
                  onChange={(e) => onUpdateConfig("slippage_model", e.target.value)}
                  className="mt-1 w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm"
                >
                  <option value="none">None</option>
                  <option value="bps">bps</option>
                </select>
              </label>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <label className="block">
                <span className="text-xs text-slate-400">Fast length (SMA/RSI)</span>
                <input
                  type="number"
                  min={1}
                  value={botConfig.fast_length ?? ""}
                  onChange={(e) => onUpdateConfig("fast_length", e.target.value)}
                  className="mt-1 w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm"
                  placeholder="14"
                />
              </label>
              <label className="block">
                <span className="text-xs text-slate-400">Slow length (SMA)</span>
                <input
                  type="number"
                  min={1}
                  value={botConfig.slow_length ?? ""}
                  onChange={(e) => onUpdateConfig("slow_length", e.target.value)}
                  className="mt-1 w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm"
                  placeholder="50"
                />
              </label>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <label className="block">
                <span className="text-xs text-slate-400">RSI entry level</span>
                <input
                  type="number"
                  min={0}
                  max={100}
                  value={botConfig.rsi_entry_level ?? ""}
                  onChange={(e) => onUpdateConfig("rsi_entry_level", e.target.value)}
                  className="mt-1 w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm"
                  placeholder="30"
                />
              </label>
              <label className="block">
                <span className="text-xs text-slate-400">RSI exit level</span>
                <input
                  type="number"
                  min={0}
                  max={100}
                  value={botConfig.rsi_exit_level ?? ""}
                  onChange={(e) => onUpdateConfig("rsi_exit_level", e.target.value)}
                  className="mt-1 w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm"
                  placeholder="70"
                />
              </label>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <label className="block">
                <span className="text-xs text-slate-400">Lookback high</span>
                <input
                  type="number"
                  min={1}
                  value={botConfig.lookback_high ?? ""}
                  onChange={(e) => onUpdateConfig("lookback_high", e.target.value)}
                  className="mt-1 w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm"
                  placeholder="20"
                />
              </label>
              <label className="block">
                <span className="text-xs text-slate-400">Stop lookback</span>
                <input
                  type="number"
                  min={1}
                  value={botConfig.stop_lookback ?? ""}
                  onChange={(e) => onUpdateConfig("stop_lookback", e.target.value)}
                  className="mt-1 w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm"
                  placeholder="10"
                />
              </label>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <label className="block">
                <span className="text-xs text-slate-400">Max risk per trade %</span>
                <input
                  type="number"
                  min={0}
                  value={botConfig.max_risk_pct ?? ""}
                  onChange={(e) => onUpdateConfig("max_risk_pct", e.target.value)}
                  className="mt-1 w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm"
                  placeholder="1"
                />
              </label>
              <label className="block">
                <span className="text-xs text-slate-400">Max daily drawdown %</span>
                <input
                  type="number"
                  min={0}
                  value={botConfig.max_daily_drawdown_pct ?? ""}
                  onChange={(e) => onUpdateConfig("max_daily_drawdown_pct", e.target.value)}
                  className="mt-1 w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm"
                  placeholder="5"
                />
              </label>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <label className="block">
                <span className="text-xs text-slate-400">Commission per trade</span>
                <input
                  type="number"
                  min={0}
                  value={botConfig.commission_per_trade}
                  onChange={(e) => onUpdateConfig("commission_per_trade", e.target.value)}
                  className="mt-1 w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm"
                />
              </label>
              <label className="block">
                <span className="text-xs text-slate-400">Commission pct</span>
                <input
                  type="number"
                  min={0}
                  value={botConfig.commission_pct}
                  onChange={(e) => onUpdateConfig("commission_pct", e.target.value)}
                  className="mt-1 w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm"
                />
              </label>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <label className="block">
                <span className="text-xs text-slate-400">Slippage (bps)</span>
                <input
                  type="number"
                  min={0}
                  value={botConfig.slippage_bps}
                  onChange={(e) => onUpdateConfig("slippage_bps", e.target.value)}
                  className="mt-1 w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm"
                />
              </label>
              <label className="block">
                <span className="text-xs text-slate-400">Starting equity</span>
                <input
                  type="number"
                  min={0}
                  value={botConfig.starting_equity}
                  onChange={(e) => onUpdateConfig("starting_equity", e.target.value)}
                  className="mt-1 w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm"
                />
              </label>
            </div>

            <label className="flex items-center gap-2 text-xs text-slate-300">
              <input
                type="checkbox"
                checked={botConfig.disableRebalance}
                onChange={(e) => onUpdateConfig("disableRebalance", e.target.checked)}
              />
              <span>Disable rebalancing (default on)</span>
            </label>

            <label className="block">
              <span className="text-xs text-slate-400">Mode</span>
              <input
                value="backtest"
                readOnly
                className="mt-1 w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-sm text-slate-400"
              />
            </label>
          </div>

          <div className="grid sm:grid-cols-2 gap-2 text-sm">
            <button
              type="button"
              onClick={onRun}
              disabled={isRunning}
              className="w-full btn-primary disabled:opacity-60 text-sm font-semibold text-center"
            >
              {isRunning ? "Running…" : "Run Backtest"}
            </button>
            <button
              type="button"
              onClick={() => onLoadChart(chartSymbol)}
              disabled={!chartSymbol || chartLoading}
              className="w-full btn-secondary disabled:opacity-60 text-sm font-semibold text-center"
            >
              {chartLoading ? "Loading…" : "Load chart"}
            </button>
          </div>
          {backtestError && <div className="text-xs text-rose-300">{backtestError}</div>}
        </div>
      </div>
    </div>
  );
}
