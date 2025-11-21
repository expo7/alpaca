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

const sampleAlerts = [
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

function renderAlerts(fetchImpl) {
  vi.stubGlobal("fetch", vi.fn(fetchImpl));
  localStorage.setItem("access", "token");
  localStorage.setItem("username", "tester");
  return render(
    <AuthProvider>
      <Alerts />
    </AuthProvider>
  );
}

describe("Alerts page", () => {
  test("renders empty state when no alerts", async () => {
    renderAlerts((url) => {
      if (url.includes("/api/alerts/")) return Promise.resolve(mockResponse([]));
      if (url.includes("/api/watchlists/")) return Promise.resolve(mockResponse([]));
      return Promise.resolve(mockResponse({}));
    });

    await waitFor(() => expect(screen.getAllByText(/Your alerts/i).length).toBeGreaterThan(0));
    expect(screen.getByText(/No alerts yet/i)).toBeInTheDocument();
  });

  test("renders alerts with key fields and supports test button state", async () => {
    const fetchImpl = vi.fn((url) => {
      if (url.includes("/api/alerts/") && url.endsWith("/")) {
        return Promise.resolve(mockResponse(sampleAlerts));
      }
      if (url.includes("/api/alerts/1/test/")) {
        return Promise.resolve(
          mockResponse({
            timestamp: "2024-01-03T12:00:00Z",
            results: [{ symbol: "AAPL", final_score: 55, triggered: true }],
          })
        );
      }
      if (url.includes("/api/watchlists/")) return Promise.resolve(mockResponse([]));
      if (url.includes("/api/alert-events/")) return Promise.resolve(mockResponse([]));
      return Promise.resolve(mockResponse({}));
    });

    renderAlerts(fetchImpl);

    await screen.findByText("AAPL");
    expect(screen.getByText(/≥ 50/)).toBeInTheDocument();
    // Trigger test flow
    const testBtn = await screen.findAllByText("Test");
    await userEvent.click(testBtn[0]);
    await waitFor(() => expect(screen.getByText(/Last test/i)).toBeInTheDocument());
  });

  test("shows error when load fails", async () => {
    renderAlerts((url) => {
      if (url.includes("/api/alerts/") && !url.includes("alert-events")) {
        return Promise.resolve(mockResponse({ detail: "boom" }, false, 500));
      }
      if (url.includes("/api/alert-events/")) return Promise.resolve(mockResponse([]));
      if (url.includes("/api/watchlists/")) return Promise.resolve(mockResponse([]));
      return Promise.resolve(mockResponse({}));
    });
    await waitFor(() => expect(screen.getByText(/boom/i)).toBeInTheDocument());
  });
});
