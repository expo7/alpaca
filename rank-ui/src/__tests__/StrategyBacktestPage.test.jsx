import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import StrategyBacktestPage from "../pages/StrategyBacktestPage.jsx";
import { AuthProvider } from "../AuthProvider.jsx";

vi.mock("recharts", async () => {
  const actual = await vi.importActual("recharts");
  return {
    ...actual,
    ResponsiveContainer: ({ children }) => (
      <div style={{ width: 400, height: 300 }}>
        {typeof children === "function"
          ? children({ width: 400, height: 300 })
          : children}
      </div>
    ),
  };
});

const mockResponse = (data, ok = true, status = 200) => ({
  ok,
  status,
  text: async () => JSON.stringify(data),
});

function renderPage(fetchImpl) {
  vi.stubGlobal("fetch", vi.fn(fetchImpl));
  localStorage.setItem("access", "token");
  localStorage.setItem("username", "tester");
  return render(
    <AuthProvider>
      <StrategyBacktestPage />
    </AuthProvider>
  );
}

const templateList = [
  {
    id: "rsi_dip_buyer",
    name: "RSI Dip Buyer",
    description: "mean reversion",
    strategy_spec: {
      entry_tree: { type: "condition", indicator: "rsi", operator: "lt", value: { param: "rsi_entry" } },
      exit_tree: { type: "condition", indicator: "rsi", operator: "gt", value: { param: "rsi_exit" } },
      parameters: {
        rsi_entry: { type: "float", default: 30 },
        rsi_exit: { type: "float", default: 55 },
      },
      metadata: {},
    },
  },
];

describe("StrategyBacktestPage", () => {
  test("loads templates, validates, and runs backtest", async () => {
    const fetchImpl = (url) => {
      if (url.includes("/api/strategies/templates/")) {
        return Promise.resolve(mockResponse(templateList));
      }
      if (url.includes("/api/strategies/validate/")) {
        return Promise.resolve(mockResponse({ valid: true, errors: [] }));
      }
      if (url.includes("/api/backtests/run/")) {
        return Promise.resolve(
          mockResponse({
            stats: {
              start_equity: 10000,
              end_equity: 10500,
              return_pct: 5,
              max_drawdown_pct: -2,
              num_trades: 2,
              win_rate_pct: 50,
            },
            equity_curve: [
              { date: "2024-01-01", value: 10000 },
              { date: "2024-01-02", value: 10500 },
            ],
            trades: [
              {
                symbol: "AAPL",
                action: "buy",
                qty: 1,
                price: 100,
                timestamp: "2024-01-02",
              },
            ],
          })
        );
      }
      return Promise.resolve(mockResponse({}));
    };

    renderPage(fetchImpl);

    await screen.findByText(/RSI Dip Buyer/i);

    await userEvent.click(screen.getByRole("button", { name: /Validate Strategy/i }));
    await waitFor(() => expect(screen.getByText(/Strategy looks valid/i)).toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: /Run Backtest/i }));
    await waitFor(() => expect(screen.getByText(/Return %/i)).toBeInTheDocument());
    expect(screen.getByText(/AAPL/)).toBeInTheDocument();
    expect(screen.getByText(/Equity curve/i)).toBeInTheDocument();
  });

  test("surfaces validation and backtest errors", async () => {
    const fetchImpl = (url) => {
      if (url.includes("/api/strategies/templates/")) {
        return Promise.resolve(mockResponse(templateList));
      }
      if (url.includes("/api/strategies/validate/")) {
        return Promise.resolve(
          mockResponse({ valid: false, errors: [{ field: "entry_tree", message: "missing" }] })
        );
      }
      if (url.includes("/api/backtests/run/")) {
        return Promise.resolve(
          mockResponse({ valid: false, errors: [{ field: "bot.symbols", message: "required" }] }, false, 400)
        );
      }
      return Promise.resolve(mockResponse({}));
    };

    renderPage(fetchImpl);
    await screen.findByText(/RSI Dip Buyer/i);

    await userEvent.click(screen.getByRole("button", { name: /Validate Strategy/i }));
    await waitFor(() => expect(screen.getAllByText(/entry_tree/i).length).toBeGreaterThan(0));

    await userEvent.click(screen.getByRole("button", { name: /Run Backtest/i }));
    await waitFor(() => expect(screen.getAllByText(/bot.symbols/i).length).toBeGreaterThan(0));
  });
});
