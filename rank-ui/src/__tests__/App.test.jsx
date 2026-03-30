import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import App from "../App.jsx";
import { AuthProvider } from "../AuthProvider.jsx";

const mockResponse = (data, ok = true, status = 200) => ({
  ok,
  status,
  json: async () => data,
});

function renderAppWithAuth() {
  return render(
    <AuthProvider>
      <App />
    </AuthProvider>
  );
}

describe("App routing and navigation smoke tests", () => {
  test("renders Landing when unauthenticated", () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(mockResponse({}))));
    renderAppWithAuth();
    expect(screen.getByText(/Make better trading decisions in seconds/i)).toBeInTheDocument();
    expect(screen.getByText(/Sign in to your dashboard/i)).toBeInTheDocument();
  });

  test("renders navbar and dashboards page when authenticated", async () => {
    // Seed token so AuthProvider treats user as logged in
    localStorage.setItem("access", "token");
    localStorage.setItem("username", "tester");
    const fetchMock = vi.fn((url) => {
      if (url.includes("/watchlists/")) return Promise.resolve(mockResponse({ results: [] }));
      if (url.includes("/api/default-tickers")) return Promise.resolve(mockResponse({ symbols: [] }));
      if (url.includes("/api/paper/orders/")) return Promise.resolve(mockResponse([]));
      if (url.includes("/api/paper/portfolios/")) return Promise.resolve(mockResponse([]));
      if (url.includes("/api/paper/leaderboards/")) return Promise.resolve(mockResponse([]));
      if (url.includes("/api/metrics/yfinance/")) return Promise.resolve(mockResponse({ count: 0 }));
      return Promise.resolve(mockResponse({ results: [] }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAppWithAuth();

    const dashboards = await screen.findAllByText(/Dashboard/i);
    expect(dashboards.length).toBeGreaterThan(0);
    // V1: Alerts and other non-dashboard tabs are hidden
    expect(screen.queryByRole("button", { name: /^Alerts$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Strategies/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Orders/i })).not.toBeInTheDocument();
  });

  test("chart button is hidden in V1 Top Opportunities rows", async () => {
    localStorage.setItem("access", "token");
    localStorage.setItem("username", "tester");

    const fetchMock = vi.fn((url) => {
      if (url.includes("/watchlists/")) return Promise.resolve(mockResponse({ results: [] }));
      if (url.includes("/api/default-tickers")) {
        return Promise.resolve(mockResponse({ symbols: ["AAPL"] }));
      }
      if (url.includes("/api/rank")) {
        return Promise.resolve(
          mockResponse({
            results: [
              {
                symbol: "AAPL",
                final_score: 72.4,
                tech_score: 70,
                fund_score: 74,
                ta_breakdown: {
                  trend_raw: 0.4,
                  momentum_raw: 0.3,
                  volume_raw: 0.2,
                  meanreversion_raw: -0.1,
                },
              },
            ],
            errors: [],
          })
        );
      }
      if (url.includes("/api/macro/dashboard")) {
        return Promise.resolve(
          mockResponse({
            regime: "Risk-On",
            confidence: 60,
            summary: "Test summary",
            themes: [],
            updated_at: "2026-03-28T12:00:00Z",
          })
        );
      }
      return Promise.resolve(mockResponse({ results: [] }));
    });

    vi.stubGlobal("fetch", fetchMock);

    renderAppWithAuth();

    await userEvent.click(await screen.findByRole("button", { name: /Update ratings|Rank/i }));

    await waitFor(() => {
      expect(screen.getByText("AAPL")).toBeInTheDocument();
    });

    // V1: action buttons are removed from Top Opportunities
    expect(screen.queryByRole("button", { name: "Chart" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Why" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Set alert/i })).not.toBeInTheDocument();
  });
});
