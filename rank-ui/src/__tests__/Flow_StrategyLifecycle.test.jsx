import { useState } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import StrategyBuilder from "../pages/StrategyBuilder.jsx";
import Orders from "../pages/Orders.jsx";
import { AuthProvider } from "../AuthProvider.jsx";

vi.mock("../hooks/useQuotes.js", () => ({
  default: () => ({}),
}));

const mockResponse = (data, ok = true, status = 200) => ({
  ok,
  status,
  json: async () => data,
});

const portfolios = [
  {
    id: 1,
    name: "Default",
    equity: 100000,
    cash_balance: 100000,
    max_single_position_pct: 0,
    max_gross_exposure_pct: 0,
  },
];

const strategies = [
  {
    id: 42,
    name: "Momentum",
    description: "Simple momentum play",
    is_active: false,
    config: {
      frequency: "1d",
      symbols: ["AAPL"],
      order_templates: {
        entry: { quantity_pct: 5, order_type: "market", side: "buy" },
        exit: { quantity_pct: 5, order_type: "market", side: "sell" },
      },
      entry: { template: "entry", rules: { type: "rule", condition: "indicator", payload: {} }, order: {} },
      exit: { template: "exit", rules: { type: "rule", condition: "indicator", payload: {} }, order: {} },
    },
  },
];

const orders = [
  {
    id: 7,
    symbol: "AAPL",
    order_type: "market",
    quantity: 10,
    status: "working",
    portfolio: 1,
    audit_events: [{ event: "liquidity_queue", bar_ts: "2024-01-01T10:00:00Z" }],
    recent_trades: [],
  },
];

function TestShell() {
  const [page, setPage] = useState("strategies");

  return (
    <AuthProvider>
      <div className="flex gap-2 mb-2">
        <button onClick={() => setPage("strategies")}>Go Strategies</button>
        <button onClick={() => setPage("orders")}>Go Orders</button>
      </div>
      {page === "strategies" ? <StrategyBuilder /> : <Orders />}
    </AuthProvider>
  );
}

describe("Flow: Strategy lifecycle", () => {
  test("user dry-runs then executes and sees queued order", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url, options = {}) => {
        const u = String(url);
        if (u.includes("/api/paper/portfolios/") && (!options.method || options.method === "GET")) {
          return Promise.resolve(mockResponse(portfolios));
        }
        if (u.includes("/api/paper/strategies/dry_run/")) {
          return Promise.resolve(mockResponse({ matches: ["AAPL"] }));
        }
        if (u.includes("/api/paper/strategies/") && u.endsWith("/execute/") && options.method === "POST") {
          return Promise.resolve(
            mockResponse({
              status: "queued",
              execution_id: "exec-123",
              portfolios: [1],
              queued_via: "celery",
            })
          );
        }
        if (u.includes("/api/paper/strategies/") && (!options.method || options.method === "GET")) {
          return Promise.resolve(mockResponse(strategies));
        }
        if (u.includes("/api/paper/quotes/")) {
          return Promise.resolve(mockResponse([{ symbol: "AAPL", price: 100 }]));
        }
        if (u.includes("/api/paper/positions/")) {
          return Promise.resolve(mockResponse({ results: [] }));
        }
        if (u.includes("/api/paper/orders/") && (!options.method || options.method === "GET")) {
          return Promise.resolve(mockResponse(orders));
        }
        if (u.includes("/api/paper/instruments/") && u.includes("?q=")) {
          return Promise.resolve(mockResponse([{ symbol: "AAPL", exchange: "NASDAQ", asset_class: "equity" }]));
        }
        if (u.includes("/api/watchlists/")) {
          return Promise.resolve(mockResponse([]));
        }
        return Promise.resolve(mockResponse({}));
      })
    );

    localStorage.setItem("access", "token");
    localStorage.setItem("username", "tester");

    render(<TestShell />);

    const strategyButton = await screen.findByText("Momentum");
    await userEvent.click(strategyButton);

    await userEvent.click(screen.getByRole("button", { name: /dry run preview/i }));
    await waitFor(() =>
      expect(screen.getByText(/Preview updated/i)).toBeInTheDocument()
    );

    const executeBtn = await screen.findByRole("button", { name: /execute/i });
    await userEvent.click(executeBtn);
    await waitFor(() =>
      expect(
        screen.getByText(/Execution queued \(exec-123\) for portfolios 1/i)
      ).toBeInTheDocument()
    );

    await userEvent.click(screen.getByText("Go Orders"));
    await screen.findByText("AAPL");
    expect(screen.getByText("⏳")).toBeInTheDocument();
  });
});
