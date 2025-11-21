import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import Backtests from "../pages/Backtests.jsx";
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

function renderBacktests(fetchImpl) {
  vi.stubGlobal("fetch", vi.fn(fetchImpl));
  localStorage.setItem("access", "token");
  localStorage.setItem("username", "tester");
  return render(
    <AuthProvider>
      <Backtests />
    </AuthProvider>
  );
}

describe("Backtests page", () => {
  test("renders saved configs and runs", async () => {
    const fetchImpl = (url, opts = {}) => {
      if (url.includes("/api/backtests/") && opts.method === "POST") {
        return Promise.resolve(mockResponse({}));
      }
      if (url.includes("/api/backtests/") && !opts.method) {
        return Promise.resolve(
          mockResponse([{ id: 1, name: "Top3", tickers: "AAPL,MSFT", start: "2024-01-01", end: "2024-02-01", initial_capital: 10000, rebalance_days: 5, top_n: 3 }])
        );
      }
      if (url.includes("/api/backtest-runs/")) {
        return Promise.resolve(mockResponse([{ id: 2, name: "Run prior", tickers: "AAPL,MSFT", start: "2024-01-01", end: "2024-02-01", initial_capital: 10000, rebalance_days: 5, top_n: 3, benchmark: "SPY" }]));
      }
      if (url.includes("/api/backtest/")) {
        return Promise.resolve(
          mockResponse({
            summary: {
              initial_capital: 10000,
              final_value: 12000,
              total_return: 0.2,
              benchmark_return: 0.05,
              alpha: 0.15,
              cagr: 0.19,
              volatility_annual: 0.12,
              sharpe_like: 1.6,
              max_drawdown: -0.1,
            },
            equity_curve: [
              { date: "2024-01-01", value: 10000 },
              { date: "2024-02-01", value: 12000 },
            ],
            benchmark: { symbol: "SPY", curve: [{ date: "2024-01-01", value: 10000 }] },
            per_ticker: [{ symbol: "AAPL", total_return: 0.2, volatility_annual: 0.1, sharpe_like: 1.1, max_drawdown: -0.05 }],
          })
        );
      }
      return Promise.resolve(mockResponse({}));
    };

    renderBacktests(fetchImpl);

    await screen.findByText(/Saved backtests/i);
    expect(screen.getByText(/Top3/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /Run backtest/i }));
    await waitFor(() => expect(screen.getByText(/Summary/i)).toBeInTheDocument());
    expect(screen.getByText(/Final value/i)).toBeInTheDocument();
    expect(screen.getByText(/Per-ticker stats/i)).toBeInTheDocument();
  });

  test("shows empty state and errors gracefully", async () => {
    const fetchImpl = (url) => {
      if (url.includes("/api/backtests/") || url.includes("/api/backtest-runs/")) {
        return Promise.resolve(mockResponse([]));
      }
      if (url.includes("/api/backtest/")) {
        return Promise.resolve(mockResponse({ detail: "failed" }, false, 400));
      }
      return Promise.resolve(mockResponse({}));
    };

    renderBacktests(fetchImpl);
    await waitFor(() => expect(screen.getByText(/Backtests/i)).toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: /Run backtest/i }));
    await waitFor(() => expect(screen.getByText(/Backtest error/i)).toBeInTheDocument());
    expect(screen.queryByText(/Saved backtests/)).toBeNull();
  });
});
