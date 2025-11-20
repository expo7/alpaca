import { useEffect, useMemo, useState } from "react";
import { useAuth } from "../AuthProvider.jsx";

const BASE = "http://127.0.0.1:8000";

const CONDITION_TYPES = [
  { value: "indicator", label: "Indicator" },
  { value: "scorer", label: "Scorer" },
  { value: "price", label: "Price" },
  { value: "volume", label: "Volume" },
  { value: "cross_symbol", label: "Cross symbol" },
  { value: "time", label: "Time" },
];

const ORDER_TYPES = [
  "market",
  "limit",
  "stop",
  "stop_limit",
  "trailing_amount",
  "trailing_percent",
  "trailing_limit",
  "market_open",
  "market_close",
  "limit_open",
  "limit_close",
  "pegged_mid",
  "pegged_primary",
  "hidden_limit",
  "iceberg",
  "algo_twap",
  "algo_vwap",
  "algo_pov",
];

const TIMEFRAMES = ["1m", "5m", "15m", "1h", "1d"];

function defaultRuleNode(type = "rule") {
  if (type === "and" || type === "or") {
    return { type, conditions: [defaultRuleNode()] };
  }
  return {
    type: "rule",
    condition: "indicator",
    payload: {
      indicator: "rsi",
      operator: "lt",
      value: 40,
      timeframe: "1d",
      window: 14,
    },
  };
}

function defaultStrategyForm() {
  return {
    name: "",
    description: "",
    frequency: "1d",
    is_active: false,
    symbols: "",
    orderTemplates: {
      entry: {
        order_type: "market",
        side: "buy",
        tif: "day",
        quantity_pct: 5,
        extended_hours: false,
      },
      exit: {
        order_type: "market",
        side: "sell",
        tif: "day",
        quantity_pct: 5,
        extended_hours: false,
      },
    },
    entry: { template: "entry", rules: defaultRuleNode(), order: {} },
    exit: { template: "exit", rules: defaultRuleNode(), order: {} },
  };
}

export default function StrategyBuilder() {
  const { token } = useAuth();
  const [strategies, setStrategies] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [form, setForm] = useState(defaultStrategyForm);
  const [status, setStatus] = useState("");
  const [dryRunMatches, setDryRunMatches] = useState([]);
  const [instrumentQuery, setInstrumentQuery] = useState("");
  const [instrumentResults, setInstrumentResults] = useState([]);
  const [instrumentLoading, setInstrumentLoading] = useState(false);
  const capHint = "Strategy-driven orders will be blocked if portfolio caps are breached.";
  const [portfolios, setPortfolios] = useState([]);
  const [selectedPortfolio, setSelectedPortfolio] = useState("");
  const [selectedPortfolios, setSelectedPortfolios] = useState([]);

  useEffect(() => {
    if (token) {
      loadStrategies();
      loadPortfolios();
    }
  }, [token]);

  async function loadPortfolios() {
    try {
      const res = await fetch(`${BASE}/api/paper/portfolios/`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      setPortfolios(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error(err);
    }
  }

  async function loadStrategies() {
    try {
      const res = await fetch(`${BASE}/api/paper/strategies/`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      setStrategies(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error(err);
    }
  }

  function resetForm() {
    setForm(defaultStrategyForm());
    setSelectedId(null);
    setDryRunMatches([]);
    setStatus("");
  }

  function parseConfig(strategy) {
    const cfg = strategy.config || {};
    return {
      name: strategy.name,
      description: strategy.description || "",
      frequency: cfg.frequency || "1d",
      is_active: strategy.is_active,
      symbols: (cfg.symbols || []).join(","),
      orderTemplates: {
        entry: {
          order_type: "market",
          side: "buy",
          tif: "day",
          quantity_pct: 5,
          extended_hours: false,
          ...(cfg.order_templates?.entry || {}),
        },
        exit: {
          order_type: "market",
          side: "sell",
          tif: "day",
          quantity_pct: 5,
          extended_hours: false,
          ...(cfg.order_templates?.exit || {}),
        },
      },
      entry: {
        template: cfg.entry?.template || "entry",
        rules: cfg.entry?.rules || defaultRuleNode(),
        order: cfg.entry?.order || {},
      },
      exit: {
        template: cfg.exit?.template || "exit",
        rules: cfg.exit?.rules || defaultRuleNode(),
        order: cfg.exit?.order || {},
      },
    };
  }

  function selectStrategy(s) {
    setSelectedId(s.id);
    setForm(parseConfig(s));
    setDryRunMatches([]);
    setStatus("");
  }

  function updateTemplate(which, field, value) {
    setForm((prev) => ({
      ...prev,
      orderTemplates: {
        ...prev.orderTemplates,
        [which]: { ...prev.orderTemplates[which], [field]: value },
      },
    }));
  }

  async function lookupInstruments() {
    if (!instrumentQuery.trim()) return;
    setInstrumentLoading(true);
    try {
      const res = await fetch(
        `${BASE}/api/paper/instruments/?q=${encodeURIComponent(instrumentQuery)}`
      );
      if (!res.ok) throw new Error("Lookup failed");
      const data = await res.json();
      setInstrumentResults(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error(err);
    } finally {
      setInstrumentLoading(false);
    }
  }

  function addSymbol(sym) {
    const existing = form.symbols
      .split(",")
      .map((s) => s.trim().toUpperCase())
      .filter(Boolean);
    if (!existing.includes(sym.toUpperCase())) {
      const next = [...existing, sym.toUpperCase()].join(",");
      setForm((prev) => ({ ...prev, symbols: next }));
    }
  }

  function updateRule(section, node) {
    setForm((prev) => ({
      ...prev,
      [section]: {
        ...prev[section],
        rules: node,
      },
    }));
  }

  function buildPayload() {
    const symbolsArray = form.symbols
      .split(",")
      .map((s) => s.trim().toUpperCase())
      .filter(Boolean);
    const targetIds =
      selectedPortfolios.length > 0
        ? selectedPortfolios
        : selectedPortfolio
        ? [selectedPortfolio]
        : [];
    return {
      name: form.name,
      description: form.description,
      is_active: form.is_active,
      config: {
        frequency: form.frequency,
        symbols: symbolsArray,
        order_templates: form.orderTemplates,
        portfolio: selectedPortfolio || null,
        portfolios: targetIds.length ? targetIds : undefined,
        entry: {
          template: form.entry.template,
          rules: form.entry.rules,
          order: form.entry.order,
        },
        exit: {
          template: form.exit.template,
          rules: form.exit.rules,
          order: form.exit.order,
        },
      },
    };
  }

  async function saveStrategy() {
    if (!token) return;
    setStatus("Saving...");
    const payload = buildPayload();
    const targetIds =
      selectedPortfolios.length > 0
        ? selectedPortfolios
        : selectedPortfolio
        ? [selectedPortfolio]
        : [];
    if (targetIds.length) {
      const blocked = targetIds.some((pid) => {
        const portfolio = portfolios.find((p) => String(p.id) === String(pid));
        const equity = Number(portfolio?.equity || portfolio?.cash_balance || 0);
        const singleCap =
          portfolio?.max_single_position_pct &&
          equity * (Number(portfolio.max_single_position_pct) / 100);
        const grossCap =
          portfolio?.max_gross_exposure_pct &&
          equity * (Number(portfolio.max_gross_exposure_pct) / 100);
        if (!singleCap && !grossCap) return false;
        const entryPct = Number(payload.config.order_templates.entry.quantity_pct || 0) / 100;
        const notionalPer = equity * entryPct;
        return (singleCap && notionalPer > singleCap) || (grossCap && notionalPer > grossCap);
      });
      if (blocked) {
        alert("Save blocked: entry template would breach caps.");
        setStatus("Save blocked by caps");
        return;
      }
    }
    const method = selectedId ? "PUT" : "POST";
    const url = selectedId
      ? `${BASE}/api/paper/strategies/${selectedId}/`
      : `${BASE}/api/paper/strategies/`;
    try {
      const res = await fetch(url, {
        method,
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error("Save failed");
      setStatus("Saved!");
      await loadStrategies();
      if (!selectedId) resetForm();
    } catch (err) {
      console.error(err);
      setStatus(err.message || "Save failed");
    }
  }

  async function validateConfig() {
    if (!token) return;
    setStatus("Validating...");
    try {
      const payload = buildPayload();
      const res = await fetch(
        `${BASE}/api/paper/strategies/validate_config/`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
        }
      );
      if (!res.ok) throw new Error("Config invalid");
      setStatus("Config looks good!");
    } catch (err) {
      console.error(err);
      setStatus(err.message || "Validation failed");
    }
  }

  async function runDryRun() {
    if (!token) return;
    setStatus("Running preview...");
    try {
      const payload = { config: buildPayload().config };
      const res = await fetch(`${BASE}/api/paper/strategies/dry_run/`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error("Dry run failed");
      const data = await res.json();
      const matches = data.matches || [];
      setDryRunMatches(matches);
      const targetIds =
        selectedPortfolios.length > 0
          ? selectedPortfolios
          : selectedPortfolio
          ? [selectedPortfolio]
          : [];
      if (matches.length && portfolios.length && targetIds.length) {
        const symbolsParam = matches.join(",");
        const quotesRes = await fetch(
          `${BASE}/api/paper/quotes/?symbols=${encodeURIComponent(symbolsParam)}`
        );
        const quotesData = await quotesRes.json();
        const quoteMap = {};
        (quotesData || []).forEach((q) => (quoteMap[q.symbol] = q.price));
        const grossRes = await fetch(`${BASE}/api/paper/positions/?limit=500`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        const grossData = await grossRes.json();
        const positions = grossData.results || [];
        for (const pid of targetIds) {
          const portfolio = portfolios.find((p) => String(p.id) === String(pid));
          const equity = Number(portfolio?.equity || portfolio?.cash_balance || 0);
          const singleCap =
            portfolio?.max_single_position_pct &&
            equity * (Number(portfolio.max_single_position_pct) / 100);
          const grossCap =
            portfolio?.max_gross_exposure_pct &&
            equity * (Number(portfolio.max_gross_exposure_pct) / 100);
          const currentGross = positions
            .filter((p) => String(p.portfolio) === String(pid))
            .reduce((sum, p) => sum + Math.abs(Number(p.market_value || 0)), 0);
          if (singleCap || grossCap) {
          const entryPct = Number(form.orderTemplates.entry.quantity_pct || 0) / 100;
          const notionalPer = equity * entryPct;
          const symbolWarns = matches.filter(
            (sym) => singleCap && notionalPer > singleCap
          );
          const projectedGross = currentGross + notionalPer * matches.length;
          if (symbolWarns.length || (grossCap && projectedGross > grossCap)) {
            setStatus("Preview blocked: caps would be breached.");
            alert("Preview blocked: caps would be breached.");
            return;
          }
        }
        }
      }
      setStatus("Preview updated");
    } catch (err) {
      console.error(err);
      setStatus(err.message || "Dry run failed");
    }
  }

  return (
    <div className="p-4 lg:p-8 space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-lg font-semibold">Strategy Builder</h1>
          <p className="text-sm text-slate-400">
            Compose rule blocks and order templates, then save or dry run.
          </p>
          <p className="text-[11px] text-amber-300">{capHint}</p>
        </div>
        <div className="flex flex-col sm:flex-row sm:items-center sm:gap-3 gap-2 text-xs">
          <span className="text-slate-500">
            Market data mode: {import.meta.env.VITE_PAPER_DATA_MODE || "live"}
          </span>
          <select
            value={selectedPortfolio}
            onChange={(e) => setSelectedPortfolio(e.target.value)}
            className="bg-slate-950 border border-slate-700 rounded-lg px-2 py-1.5"
          >
            <option value="">Select portfolio for caps</option>
            {portfolios.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} (single {p.max_single_position_pct || "—"}% gross {p.max_gross_exposure_pct || "—"}%)
              </option>
            ))}
          </select>
          <div className="flex flex-col gap-1">
            <span className="text-[11px] text-slate-500">Multi-target cap check</span>
            <select
              multiple
              value={selectedPortfolios}
              onChange={(e) =>
                setSelectedPortfolios(
                  Array.from(e.target.selectedOptions).map((opt) => opt.value)
                )
              }
              className="bg-slate-950 border border-slate-700 rounded-lg px-2 py-1.5 min-w-[200px] h-16"
            >
              {portfolios.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>
          <button
            type="button"
            onClick={validateConfig}
            className="px-3 py-1.5 rounded-xl border border-slate-600 text-xs"
          >
            Validate config
          </button>
          <button
            type="button"
            onClick={runDryRun}
            className="px-3 py-1.5 rounded-xl border border-slate-600 text-xs"
          >
            Dry run preview
          </button>
          <button
            type="button"
            onClick={saveStrategy}
            className="px-4 py-1.5 rounded-xl bg-indigo-600 text-white text-xs"
          >
            Save strategy
          </button>
          <button
            type="button"
            onClick={resetForm}
            className="px-3 py-1.5 rounded-xl border border-slate-600 text-xs"
          >
            New
          </button>
        </div>
      </div>

      {status && (
        <div className="text-xs text-amber-200 bg-amber-900/30 border border-amber-800 rounded-xl px-3 py-2">
          {status}
        </div>
      )}

      {dryRunMatches.length > 0 && (
        <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-3 text-xs">
          <div className="font-semibold mb-2">
            Preview matches ({dryRunMatches.length})
          </div>
          <div className="flex flex-wrap gap-2">
            {dryRunMatches.map((sym) => (
              <span
                key={sym}
                className="px-2 py-1 rounded-full bg-emerald-600/20 border border-emerald-700 text-emerald-100"
              >
                {sym}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="grid lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-4">
          <StrategyForm
            form={form}
            setForm={setForm}
            instrumentQuery={instrumentQuery}
            setInstrumentQuery={setInstrumentQuery}
            instrumentResults={instrumentResults}
            instrumentLoading={instrumentLoading}
            lookupInstruments={lookupInstruments}
            addSymbol={addSymbol}
          />

          <OrderTemplateEditor
            title="Entry template"
            template={form.orderTemplates.entry}
            onChange={(field, value) => updateTemplate("entry", field, value)}
          />
          <OrderTemplateEditor
            title="Exit template"
            template={form.orderTemplates.exit}
            onChange={(field, value) => updateTemplate("exit", field, value)}
          />

          <RuleSection
            title="Entry rules"
            section="entry"
            data={form.entry}
            onTemplateChange={(value) =>
              setForm((prev) => ({
                ...prev,
                entry: { ...prev.entry, template: value },
              }))
            }
            onRuleChange={(node) => updateRule("entry", node)}
          />

          <RuleSection
            title="Exit rules"
            section="exit"
            data={form.exit}
            onTemplateChange={(value) =>
              setForm((prev) => ({
                ...prev,
                exit: { ...prev.exit, template: value },
              }))
            }
            onRuleChange={(node) => updateRule("exit", node)}
          />
        </div>

        <aside className="space-y-4">
          <StrategyList
            strategies={strategies}
            selectedId={selectedId}
            onSelect={selectStrategy}
          />
        </aside>
      </div>
    </div>
  );
}

function StrategyForm({
  form,
  setForm,
  instrumentQuery,
  setInstrumentQuery,
  instrumentResults,
  instrumentLoading,
  lookupInstruments,
  addSymbol,
}) {
  return (
    <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-4 space-y-3">
      <div className="grid sm:grid-cols-2 gap-3">
        <div>
          <label className="block text-xs mb-1 text-slate-400">Name</label>
          <input
            className="w-full rounded-lg bg-slate-950 border border-slate-800 px-3 py-2 text-sm"
            value={form.name}
            onChange={(e) =>
              setForm((prev) => ({ ...prev, name: e.target.value }))
            }
          />
        </div>
        <div>
          <label className="block text-xs mb-1 text-slate-400">Frequency</label>
          <select
            className="w-full rounded-lg bg-slate-950 border border-slate-800 px-3 py-2 text-sm"
            value={form.frequency}
            onChange={(e) =>
              setForm((prev) => ({ ...prev, frequency: e.target.value }))
            }
          >
            {["1m", "5m", "15m", "1h", "1d"].map((freq) => (
              <option key={freq} value={freq}>
                {freq}
              </option>
            ))}
          </select>
        </div>
      </div>
      <div>
        <label className="block text-xs mb-1 text-slate-400">Symbols</label>
        <textarea
          className="w-full rounded-lg bg-slate-950 border border-slate-800 px-3 py-2 text-sm"
          rows={2}
          value={form.symbols}
          onChange={(e) =>
            setForm((prev) => ({ ...prev, symbols: e.target.value }))
          }
          placeholder="AAPL, MSFT, NVDA"
        />
        <div className="mt-2 space-y-2 text-xs">
          <div className="flex gap-2">
            <input
              className="flex-1 rounded-lg bg-slate-950 border border-slate-800 px-3 py-2"
              value={instrumentQuery}
              onChange={(e) => setInstrumentQuery(e.target.value)}
              placeholder="Lookup symbol…"
            />
            <button
              type="button"
              onClick={lookupInstruments}
              className="px-3 py-2 rounded-lg border border-slate-700"
            >
              {instrumentLoading ? "..." : "Search"}
            </button>
          </div>
          {instrumentResults.length > 0 && (
            <div className="bg-slate-950 border border-slate-800 rounded-lg max-h-32 overflow-auto">
              {instrumentResults.map((inst) => (
                <button
                  key={inst.id || inst.symbol}
                  type="button"
                  className="w-full text-left px-3 py-1.5 hover:bg-slate-800 flex justify-between"
                  onClick={() => addSymbol(inst.symbol)}
                >
                  <span className="font-semibold">{inst.symbol}</span>
                  <span className="text-slate-400 text-right">
                    {inst.exchange ? `${inst.exchange} · ` : ""}
                    {inst.asset_class}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
      <div>
        <label className="block text-xs mb-1 text-slate-400">Description</label>
        <textarea
          className="w-full rounded-lg bg-slate-950 border border-slate-800 px-3 py-2 text-sm"
          rows={2}
          value={form.description}
          onChange={(e) =>
            setForm((prev) => ({ ...prev, description: e.target.value }))
          }
        />
      </div>
      <label className="inline-flex items-center gap-2 text-xs text-slate-300">
        <input
          type="checkbox"
          checked={form.is_active}
          onChange={(e) =>
            setForm((prev) => ({ ...prev, is_active: e.target.checked }))
          }
        />
        Strategy active
      </label>
    </div>
  );
}

function StrategyList({ strategies, selectedId, onSelect }) {
  return (
    <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-4 space-y-3">
      <div className="text-sm font-semibold">Existing strategies</div>
      <div className="space-y-2 max-h-[500px] overflow-y-auto">
        {strategies.map((strat) => (
          <button
            key={strat.id}
            type="button"
            onClick={() => onSelect(strat)}
            className={`w-full text-left px-3 py-2 rounded-lg border text-sm ${
              selectedId === strat.id
                ? "border-indigo-500 bg-indigo-600/20"
                : "border-slate-700 bg-slate-900 hover:bg-slate-800"
            }`}
          >
            <div className="font-semibold">{strat.name}</div>
            <div className="text-xs text-slate-400">
              {strat.description || "—"}
            </div>
            <div className="text-[11px] text-slate-500 mt-1">
              {strat.config?.symbols?.length || 0} symbols · freq{" "}
              {strat.config?.frequency || "?"}
            </div>
          </button>
        ))}
        {!strategies.length && (
          <div className="text-xs text-slate-500">
            No strategies yet. Create one on the left.
          </div>
        )}
      </div>
    </div>
  );
}

function OrderTemplateEditor({ title, template, onChange }) {
  return (
    <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-4 space-y-3">
      <div className="text-sm font-semibold">{title}</div>
      <div className="grid md:grid-cols-3 gap-3 text-xs">
        <div>
          <label className="block mb-1 text-slate-400">Order type</label>
          <select
            className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5"
            value={template.order_type}
            onChange={(e) => onChange("order_type", e.target.value)}
          >
            {ORDER_TYPES.map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block mb-1 text-slate-400">Side</label>
          <select
            className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5"
            value={template.side}
            onChange={(e) => onChange("side", e.target.value)}
          >
            <option value="buy">Buy</option>
            <option value="sell">Sell</option>
          </select>
        </div>
        <div>
          <label className="block mb-1 text-slate-400">Time in force</label>
          <select
            className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5"
            value={template.tif}
            onChange={(e) => onChange("tif", e.target.value)}
          >
            {["day", "gtc", "gtd", "ioc", "fok", "aon", "opg", "cls", "ext"].map(
              (opt) => (
                <option key={opt} value={opt}>
                  {opt.toUpperCase()}
                </option>
              )
            )}
          </select>
        </div>
      </div>
      <div className="grid sm:grid-cols-2 gap-3 text-xs">
        <TextField
          label="Quantity (shares)"
          value={template.quantity || ""}
          onChange={(val) => onChange("quantity", val)}
        />
        <TextField
          label="Quantity % equity"
          value={template.quantity_pct || ""}
          onChange={(val) => onChange("quantity_pct", val)}
        />
        <TextField
          label="Notional (USD)"
          value={template.notional || ""}
          onChange={(val) => onChange("notional", val)}
        />
        <TextField
          label="Limit price"
          value={template.limit_price || ""}
          onChange={(val) => onChange("limit_price", val)}
        />
        <TextField
          label="Stop price"
          value={template.stop_price || ""}
          onChange={(val) => onChange("stop_price", val)}
        />
        <TextField
          label="Trail amount"
          value={template.trail_amount || ""}
          onChange={(val) => onChange("trail_amount", val)}
        />
        <TextField
          label="Trail percent"
          value={template.trail_percent || ""}
          onChange={(val) => onChange("trail_percent", val)}
        />
      </div>
      <label className="inline-flex items-center gap-2 text-xs text-slate-300">
        <input
          type="checkbox"
          checked={template.extended_hours || false}
          onChange={(e) => onChange("extended_hours", e.target.checked)}
        />
        Extended hours
      </label>
    </div>
  );
}

function RuleSection({
  title,
  data,
  section,
  onTemplateChange,
  onRuleChange,
}) {
  return (
    <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-4 space-y-3">
      <div className="flex items-center gap-3">
        <div className="text-sm font-semibold">{title}</div>
        <select
          className="text-xs rounded-lg border border-slate-800 bg-slate-950 px-2 py-1"
          value={data.template}
          onChange={(e) => onTemplateChange(e.target.value)}
        >
          <option value="">No template</option>
          <option value="entry">Entry template</option>
          <option value="exit">Exit template</option>
        </select>
      </div>
      <RuleNodeEditor node={data.rules} onChange={onRuleChange} depth={0} />
    </div>
  );
}

function RuleNodeEditor({ node, onChange, depth }) {
  const typeValue = node.type || "rule";

  function handleTypeChange(value) {
    if (value === "and" || value === "or") {
      onChange(
        node.type === value
          ? node
          : { type: value, conditions: node.conditions || [defaultRuleNode()] }
      );
    } else {
      onChange(defaultRuleNode());
    }
  }

  if (typeValue === "and" || typeValue === "or") {
    const conditions = node.conditions || [];
    return (
      <div className="border border-slate-800 rounded-xl p-3 space-y-2 bg-slate-950/40">
        <div className="flex items-center gap-2 text-xs">
          <select
            value={typeValue}
            onChange={(e) => handleTypeChange(e.target.value)}
            className="rounded-lg border border-slate-800 bg-slate-950 px-2 py-1"
          >
            <option value="and">AND group</option>
            <option value="or">OR group</option>
            <option value="rule">Convert to rule</option>
          </select>
          <button
            type="button"
            className="px-2 py-1 rounded-lg border border-slate-800 text-[11px]"
            onClick={() =>
              onChange({
                ...node,
                conditions: [...conditions, defaultRuleNode()],
              })
            }
          >
            + condition
          </button>
        </div>
        <div className="space-y-2">
          {conditions.map((child, idx) => (
            <div key={idx} className="relative">
              <RuleNodeEditor
                node={child}
                depth={depth + 1}
                onChange={(updated) => {
                  const next = conditions.slice();
                  next[idx] = updated;
                  onChange({ ...node, conditions: next });
                }}
              />
              <button
                type="button"
                className="absolute top-1 right-1 text-[10px] text-slate-400"
                onClick={() => {
                  const next = conditions.filter((_, i) => i !== idx);
                  onChange({ ...node, conditions: next });
                }}
              >
                ✕
              </button>
            </div>
          ))}
          {!conditions.length && (
            <div className="text-xs text-slate-500">
              Add at least one condition.
            </div>
          )}
        </div>
      </div>
    );
  }

  const payload = node.payload || {};
  return (
    <div className="border border-slate-800 rounded-xl p-3 space-y-2 bg-slate-950/70">
      <div className="flex items-center gap-2 text-xs">
        <select
          value={node.condition || "indicator"}
          onChange={(e) =>
            onChange({
              ...node,
              condition: e.target.value,
              payload: payloadDefaults(e.target.value),
            })
          }
          className="rounded-lg border border-slate-800 bg-slate-950 px-2 py-1"
        >
          {CONDITION_TYPES.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        <button
          type="button"
          className="px-2 py-1 rounded-lg border border-slate-800 text-[11px]"
          onClick={() => handleTypeChange("and")}
        >
          Convert to group
        </button>
      </div>
      <ConditionFields
        condition={node.condition || "indicator"}
        payload={payload}
        onChange={(next) => onChange({ ...node, payload: next })}
      />
    </div>
  );
}

function payloadDefaults(type) {
  const defaults = {
    indicator: {
      indicator: "rsi",
      operator: "lt",
      value: 40,
      timeframe: "1d",
      window: 14,
    },
    scorer: {
      field: "final_score",
      operator: "gt",
      value: 70,
    },
    price: { operator: "gt", value: 0 },
    volume: { operator: "gt", value: 1000000, basis: "current" },
    cross_symbol: { symbol: "QQQ", operator: "gt", value: 0 },
    time: { timestamp: new Date().toISOString() },
  };
  return defaults[type] || {};
}

function ConditionFields({ condition, payload, onChange }) {
  switch (condition) {
    case "indicator":
      return (
        <div className="grid sm:grid-cols-2 gap-2 text-xs">
          <SelectField
            label="Indicator"
            value={payload.indicator}
            options={["rsi", "sma", "ema", "volume"]}
            onChange={(val) => onChange({ ...payload, indicator: val })}
          />
          <SelectField
            label="Operator"
            value={payload.operator}
            options={["gt", "gte", "lt", "lte", "eq"]}
            onChange={(val) => onChange({ ...payload, operator: val })}
          />
          <TextField
            label="Value"
            value={payload.value ?? ""}
            onChange={(val) => onChange({ ...payload, value: Number(val) })}
          />
          <SelectField
            label="Timeframe"
            value={payload.timeframe || "1d"}
            options={TIMEFRAMES}
            onChange={(val) => onChange({ ...payload, timeframe: val })}
          />
          <TextField
            label="Window"
            value={payload.window ?? ""}
            onChange={(val) => onChange({ ...payload, window: Number(val) })}
          />
        </div>
      );
    case "scorer":
      return (
        <div className="grid sm:grid-cols-2 gap-2 text-xs">
          <TextField
            label="Field"
            value={payload.field || "final_score"}
            onChange={(val) => onChange({ ...payload, field: val })}
          />
          <SelectField
            label="Operator"
            value={payload.operator}
            options={["gt", "gte", "lt", "lte", "eq"]}
            onChange={(val) => onChange({ ...payload, operator: val })}
          />
          <TextField
            label="Value"
            value={payload.value ?? ""}
            onChange={(val) => onChange({ ...payload, value: Number(val) })}
          />
        </div>
      );
    case "price":
      return (
        <div className="grid sm:grid-cols-2 gap-2 text-xs">
          <SelectField
            label="Operator"
            value={payload.operator}
            options={["gt", "gte", "lt", "lte", "eq"]}
            onChange={(val) => onChange({ ...payload, operator: val })}
          />
          <TextField
            label="Value"
            value={payload.value ?? ""}
            onChange={(val) => onChange({ ...payload, value: Number(val) })}
          />
        </div>
      );
    case "volume":
      return (
        <div className="grid sm:grid-cols-2 gap-2 text-xs">
          <SelectField
            label="Operator"
            value={payload.operator}
            options={["gt", "gte", "lt", "lte", "eq"]}
            onChange={(val) => onChange({ ...payload, operator: val })}
          />
          <TextField
            label="Value"
            value={payload.value ?? ""}
            onChange={(val) => onChange({ ...payload, value: Number(val) })}
          />
          <SelectField
            label="Basis"
            value={payload.basis || "current"}
            options={["current", "average"]}
            onChange={(val) => onChange({ ...payload, basis: val })}
          />
          <TextField
            label="Window"
            value={payload.window ?? ""}
            onChange={(val) => onChange({ ...payload, window: Number(val) })}
          />
        </div>
      );
    case "cross_symbol":
      return (
        <div className="grid sm:grid-cols-2 gap-2 text-xs">
          <TextField
            label="Symbol"
            value={payload.symbol || ""}
            onChange={(val) => onChange({ ...payload, symbol: val })}
          />
          <TextField
            label="Compare symbol"
            value={payload.compare_symbol || ""}
            onChange={(val) => onChange({ ...payload, compare_symbol: val })}
          />
          <SelectField
            label="Operator"
            value={payload.operator}
            options={["gt", "gte", "lt", "lte", "eq"]}
            onChange={(val) => onChange({ ...payload, operator: val })}
          />
          <TextField
            label="Value (optional)"
            value={payload.value ?? ""}
            onChange={(val) => onChange({ ...payload, value: Number(val) })}
          />
        </div>
      );
    case "time":
      return (
        <div className="text-xs">
          <TextField
            label="Timestamp"
            value={payload.timestamp || ""}
            onChange={(val) => onChange({ ...payload, timestamp: val })}
          />
        </div>
      );
    default:
      return null;
  }
}

function TextField({ label, value, onChange }) {
  return (
    <div>
      <label className="block mb-1 text-slate-400">{label}</label>
      <input
        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}

function SelectField({ label, value, options, onChange }) {
  return (
    <div>
      <label className="block mb-1 text-slate-400">{label}</label>
      <select
        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        {options.map((opt) => (
          <option key={opt} value={opt}>
            {opt}
          </option>
        ))}
      </select>
    </div>
  );
}
