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
    expect(screen.getByText(/Rank stocks by/i)).toBeInTheDocument();
    expect(screen.getByText(/Sign in to your dashboard/i)).toBeInTheDocument();
  });

  test("renders navbar and switches pages when authenticated", async () => {
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
    // Strategies tab
    await userEvent.click(screen.getAllByRole("button", { name: /Strategies/i })[0]);
    await waitFor(() => expect(screen.getByText(/Strategy Builder/i)).toBeInTheDocument());

    // Orders tab
    await userEvent.click(screen.getAllByRole("button", { name: /Orders/i })[0]);
    await waitFor(() => expect(screen.getByText(/Inline-manage bracket/i)).toBeInTheDocument());
  });
});
