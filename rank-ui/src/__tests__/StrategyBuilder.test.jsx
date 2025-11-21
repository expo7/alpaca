import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import StrategyBuilder from "../pages/StrategyBuilder.jsx";
import { AuthProvider } from "../AuthProvider.jsx";

const mockResponse = (data, ok = true, status = 200) => ({
  ok,
  status,
  json: async () => data,
});

const samplePortfolios = [
  {
    id: 1,
    name: "Default",
    equity: 100000,
    cash_balance: 100000,
    max_single_position_pct: 0,
    max_gross_exposure_pct: 0,
  },
];

const sampleStrategies = [
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

function renderWithAuth(fetchImpl) {
  vi.stubGlobal("fetch", vi.fn(fetchImpl));
  localStorage.setItem("access", "test-token");
  localStorage.setItem("username", "tester");
  return render(
    <AuthProvider>
      <StrategyBuilder />
    </AuthProvider>
  );
}

describe("StrategyBuilder", () => {
  test("renders list, selects a strategy, and updates dry-run status", async () => {
    const fetchImpl = (url, options = {}) => {
      if (url.includes("/api/paper/portfolios/") && (!options.method || options.method === "GET")) {
        return Promise.resolve(mockResponse(samplePortfolios));
      }
      if (url.includes("/api/paper/strategies/") && (!options.method || options.method === "GET")) {
        return Promise.resolve(mockResponse(sampleStrategies));
      }
      if (url.includes("/api/paper/strategies/dry_run/")) {
        return Promise.resolve(mockResponse({ matches: ["AAPL"] }));
      }
      if (url.includes("/api/paper/quotes/")) {
        return Promise.resolve(mockResponse([{ symbol: "AAPL", price: 100 }]));
      }
      if (url.includes("/api/paper/positions/")) {
        return Promise.resolve(mockResponse({ results: [] }));
      }
      return Promise.resolve(mockResponse({}));
    };

    renderWithAuth(fetchImpl);

    const strategyButton = await screen.findByText("Momentum");
    await userEvent.click(strategyButton);
    await waitFor(() =>
      expect(screen.getByDisplayValue("Momentum")).toBeInTheDocument()
    );

    await userEvent.click(screen.getByRole("button", { name: /dry run preview/i }));
    await waitFor(() =>
      expect(screen.getByText(/Preview updated/i)).toBeInTheDocument()
    );
  });

  test("executes a strategy, shows loading, then shows queued response", async () => {
    let resolveExecute;
    const executePromise = new Promise((resolve) => {
      resolveExecute = resolve;
    });
    const fetchImpl = (url, options = {}) => {
      if (url.includes("/execute/") && options.method === "POST") {
        return executePromise;
      }
      if (url.includes("/api/paper/portfolios/") && (!options.method || options.method === "GET")) {
        return Promise.resolve(mockResponse(samplePortfolios));
      }
      if (url.includes("/api/paper/strategies/") && (!options.method || options.method === "GET")) {
        return Promise.resolve(mockResponse(sampleStrategies));
      }
      return Promise.resolve(mockResponse({}));
    };

    renderWithAuth(fetchImpl);
    const strategyButton = await screen.findByText("Momentum");
    await userEvent.click(strategyButton);
    const executeBtn = await screen.findByRole("button", { name: /execute/i });

    await userEvent.click(executeBtn);
    expect(executeBtn).toBeDisabled();
    expect(executeBtn).toHaveTextContent(/Executing.../i);

    resolveExecute(
      mockResponse({
        status: "queued",
        execution_id: "exec-1",
        portfolios: [1],
        queued_via: "celery",
      })
    );

    await waitFor(() =>
      expect(
        screen.getByText(/Execution queued \(exec-1\) for portfolios 1 \[via celery]/i)
      ).toBeInTheDocument()
    );
  });

  test("surfaces API errors when execution fails", async () => {
    const fetchImpl = (url, options = {}) => {
      if (url.includes("/execute/") && options.method === "POST") {
        return Promise.resolve(mockResponse({ detail: "Cap breach" }, false, 400));
      }
      if (url.includes("/api/paper/portfolios/") && (!options.method || options.method === "GET")) {
        return Promise.resolve(mockResponse(samplePortfolios));
      }
      if (url.includes("/api/paper/strategies/") && (!options.method || options.method === "GET")) {
        return Promise.resolve(mockResponse(sampleStrategies));
      }
      return Promise.resolve(mockResponse({}));
    };

    renderWithAuth(fetchImpl);
    const strategyButton = await screen.findByText("Momentum");
    await userEvent.click(strategyButton);
    const executeBtn = await screen.findByRole("button", { name: /execute/i });
    await userEvent.click(executeBtn);

    await waitFor(() =>
      expect(
        screen.getByText(/Execution failed: Cap breach/i)
      ).toBeInTheDocument()
    );
  });
});
