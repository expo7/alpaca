import { render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import Performance from "../pages/Performance.jsx";
import { AuthProvider } from "../AuthProvider.jsx";

const mockResponse = (data, ok = true, status = 200) => ({
  ok,
  status,
  json: async () => data,
});

function renderPerformance(fetchImpl) {
  vi.stubGlobal("fetch", vi.fn(fetchImpl));
  localStorage.setItem("access", "token");
  return render(
    <AuthProvider>
      <Performance />
    </AuthProvider>
  );
}

describe("Performance page", () => {
  test("renders metrics and snapshots", async () => {
    const fetchImpl = (url) => {
      if (url.includes("cash-movements")) {
        return Promise.resolve(
          mockResponse([
            {
              id: 1,
              amount: 1000,
              reason: "deposit",
              movement_type: "deposit",
              created_at: "2024-01-03T00:00:00Z",
            },
          ])
        );
      }
      if (url.includes("/performance/") && url.includes("snapshots")) {
        return Promise.resolve(
          mockResponse([
            {
              id: 1,
              timestamp: "2024-01-01T00:00:00Z",
              equity: 10000,
              cash: 2000,
              realized_pnl: 100,
              unrealized_pnl: 50,
            },
            {
              id: 2,
              timestamp: "2024-01-02T00:00:00Z",
              equity: 11000,
              cash: 2500,
              realized_pnl: 150,
              unrealized_pnl: 70,
            },
          ])
        );
      }
      if (url.includes("/performance/") && !url.includes("snapshots")) {
        return Promise.resolve(
          mockResponse({
            equity: 11000,
            cash: 5000,
            total_return_pct: 10,
            realized_pnl: 200,
            unrealized_pnl: 300,
            days_active: 5,
          })
        );
      }
      if (url.includes("/api/paper/portfolios/") && !url.includes("performance")) {
        return Promise.resolve(mockResponse([{ id: 1, name: "Paper", base_currency: "USD" }]));
      }
      return Promise.resolve(mockResponse({}));
    };

    renderPerformance(fetchImpl);

    await screen.findByText(/Portfolio Performance/i);
    await waitFor(() => expect(screen.getAllByText(/\$11000\.00/).length).toBeGreaterThan(0));
    expect(screen.getAllByText(/\$5000\.00/).length).toBeGreaterThan(0);
    expect(screen.getByText(/10\.00%/)).toBeInTheDocument();
    expect(screen.getAllByText(/deposit/i).length).toBeGreaterThan(0);
    await waitFor(() => expect(screen.getAllByText(/\$1,000/).length).toBeGreaterThan(0));
  });

  test("shows error on failure", async () => {
    const fetchImpl = (url) => {
      if (url.includes("/api/paper/portfolios/") && !url.includes("performance")) {
        return Promise.resolve(mockResponse([{ id: 1, name: "Paper" }]));
      }
      if (url.includes("/performance/") && !url.includes("snapshots")) {
        return Promise.resolve(mockResponse({ detail: "boom" }, false, 500));
      }
      return Promise.resolve(mockResponse({}));
    };
    renderPerformance(fetchImpl);
    await waitFor(() => expect(screen.getByText(/Failed to load performance data/i)).toBeInTheDocument());
  });
});
