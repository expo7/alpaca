import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
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

const sampleOrder = {
  id: 1,
  symbol: "AAPL",
  order_type: "limit",
  quantity: 10,
  status: "working",
  portfolio: 1,
  audit_events: [{ event: "liquidity_queue", bar_ts: "2024-01-01T10:00:00Z" }],
  recent_trades: [{ id: 10, side: "buy", quantity: 5, price: "10.00", fees: "0.00", slippage: "0.00", created_at: "2024-01-01T10:00:00Z" }],
};

const samplePortfolio = { id: 1, name: "Paper", equity: 10000, max_single_position_pct: 0, max_gross_exposure_pct: 0 };

function renderOrders(fetchImpl) {
  vi.stubGlobal("fetch", vi.fn(fetchImpl));
  localStorage.setItem("access", "token");
  localStorage.setItem("username", "tester");
  return render(
    <AuthProvider>
      <Orders />
    </AuthProvider>
  );
}

describe("Orders page", () => {
  test("shows queued/pending chips and opens detail modal with timeline", async () => {
    const fetchImpl = (url, options = {}) => {
      if (url.includes("/api/paper/orders/") && (!options.method || options.method === "GET")) {
        return Promise.resolve(mockResponse([sampleOrder]));
      }
      if (url.includes("/api/paper/portfolios/") && (!options.method || options.method === "GET")) {
        return Promise.resolve(mockResponse([samplePortfolio]));
      }
      if (url.includes("/api/watchlists/")) {
        return Promise.resolve(mockResponse([]));
      }
      if (url.includes("/api/paper/instruments/") && url.includes("?q=")) {
        return Promise.resolve(mockResponse([{ symbol: "AAPL", exchange: "NASDAQ", asset_class: "equity" }]));
      }
      return Promise.resolve(mockResponse({}));
    };

    renderOrders(fetchImpl);

    await screen.findByText("AAPL");
    const etaChips = screen.getAllByTitle(/next bar/i);
    expect(etaChips.length).toBeGreaterThan(0);
    expect(screen.getByText("⏳")).toBeInTheDocument();

    await userEvent.click(screen.getByText("AAPL"));
    await waitFor(() =>
      expect(
        screen.getByText(/Audit · Order #1 \(AAPL\)/i)
      ).toBeInTheDocument()
    );
    const eventsLabels = screen.getAllByText(/Events/i);
    expect(eventsLabels.length).toBeGreaterThan(0);
  });
});
