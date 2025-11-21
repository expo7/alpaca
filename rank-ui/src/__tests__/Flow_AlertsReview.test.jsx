import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import Alerts from "../pages/Alerts.jsx";
import { AuthProvider } from "../AuthProvider.jsx";

const mockResponse = (data, ok = true, status = 200) => ({
  ok,
  status,
  json: async () => data,
  text: async () => JSON.stringify(data),
});

describe("Flow: Alerts review and history drill-down", () => {
  test("user views alert, opens history, and clears it", async () => {
    const alerts = [
      {
        id: 1,
        alert_type: "symbol",
        symbol: "AAPL",
        min_final_score: 50,
        min_tech_score: 40,
        min_fund_score: 30,
        active: true,
        last_triggered_at: "2024-01-02T12:00:00Z",
      },
    ];

    const history = [
      {
        id: 101,
        alert_id: 1,
        symbol: "AAPL",
        final_score: 55,
        tech_score: 42,
        fund_score: 33,
        triggered_at: "2024-01-02T12:00:00Z",
      },
    ];

    let historyCalls = 0;

    const fetchImpl = vi.fn((url, options = {}) => {
      const u = String(url);
      if (u.includes("/api/alerts/") && !u.includes("/test/") && !options.method) {
        return Promise.resolve(mockResponse(alerts));
      }
      if (u.includes("/api/watchlists/")) {
        return Promise.resolve(mockResponse([]));
      }
      if (u.includes("/api/alerts/1/test/")) {
        return Promise.resolve(
          mockResponse({
            timestamp: "2024-01-03T12:00:00Z",
            results: [{ symbol: "AAPL", final_score: 57, triggered: true }],
          })
        );
      }
      if (u.includes("/api/alert-events/")) {
        historyCalls += 1;
        const hasSymbolFilter = u.includes("symbol=");
        if (hasSymbolFilter || historyCalls === 1) {
          return Promise.resolve(mockResponse({ results: history }));
        }
        return Promise.resolve(mockResponse({ results: [] }));
      }
      return Promise.resolve(mockResponse({}));
    });

    vi.stubGlobal("fetch", fetchImpl);
    localStorage.setItem("access", "token");
    localStorage.setItem("username", "tester");

    render(
      <AuthProvider>
        <Alerts />
      </AuthProvider>
    );

    const alertCells = await screen.findAllByText("AAPL");
    expect(alertCells.length).toBeGreaterThan(0);

    // Open inline details via Test
    const testBtn = await screen.findByText("Test");
    await userEvent.click(testBtn);
    await waitFor(() => expect(screen.getByText(/Last test/i)).toBeInTheDocument());

    // Drill into history panel with a filter
    const filterInput = screen.getByPlaceholderText(/Filter by symbol/i);
    await userEvent.type(filterInput, "AAPL");
    await userEvent.click(screen.getByRole("button", { name: /Apply/i }));
    await waitFor(() => expect(screen.getByText("#1")).toBeInTheDocument());

    // Close/clear history view
    await userEvent.click(screen.getByRole("button", { name: /Reset/i }));
    await waitFor(() =>
      expect(screen.queryByText("#1")).not.toBeInTheDocument()
    );
  });
});
