import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import Orders from "../pages/Orders.jsx";
import { AuthProvider } from "../AuthProvider.jsx";

const { mockQuotes, useQuotesMock } = vi.hoisted(() => {
  const mockQuotes = { AAPL: 12.34 };
  const emptyQuotes = {};
  const useQuotesMock = vi.fn((symbols = []) => {
    if (!Array.isArray(symbols) || !symbols.length) return emptyQuotes;
    return mockQuotes;
  });
  return { mockQuotes, useQuotesMock };
});

vi.mock("../hooks/useQuotes.js", () => ({
  default: useQuotesMock,
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

const defaultFetchImpl = (url, options = {}) => {
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
  if (url.includes("/api/paper/symbols/") && url.includes("/interval/")) {
    return Promise.resolve(
      mockResponse({
        symbol: "AAPL",
        interval: "1m",
        period: "max",
        last_close: mockQuotes.AAPL,
        candles: [],
      })
    );
  }
  return Promise.resolve(mockResponse({}));
};

function renderOrders(fetchImpl = defaultFetchImpl) {
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
  beforeEach(() => {
    useQuotesMock.mockReset();
    useQuotesMock.mockImplementation((symbols = []) => {
      if (!Array.isArray(symbols) || !symbols.length) return {};
      const out = {};
      symbols.forEach((sym) => {
        const key = sym?.toUpperCase();
        if (mockQuotes[key] !== undefined) out[key] = mockQuotes[key];
      });
      return out;
    });
  });

  test("shows queued/pending chips and opens detail modal with timeline", async () => {
    renderOrders();

    await screen.findByText("AAPL");
    const row = screen.getByText("AAPL").closest("tr");
    expect(within(row).getByText(/Live: \$12\.34/)).toBeInTheDocument();
    expect(within(row).getByText(/Est\. notional:\s*\$123\.40/)).toBeInTheDocument();
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

  test("surface live price and estimated cost in Price & Cost card", async () => {
    renderOrders();

    await screen.findByText("AAPL");

    const symbolInput = screen.getByPlaceholderText(/^Symbol$/i);
    await userEvent.clear(symbolInput);
    await userEvent.type(symbolInput, "AAPL");
    await userEvent.click(screen.getByText(/Set symbol/i));

    const qtyInput = screen.getByPlaceholderText(/Quantity/i);
    await userEvent.clear(qtyInput);
    await userEvent.type(qtyInput, "5");
    await userEvent.click(screen.getByText(/Get 1m price/i));

    const priceCardHeading = screen.getByText(/Price & Cost/i);
    const priceCard = priceCardHeading.parentElement?.parentElement;
    expect(priceCard).toBeTruthy();

    await waitFor(() => {
      expect(within(priceCard).getByText(/\$12\.34/)).toBeInTheDocument();
      expect(within(priceCard).getByText(/\$61\.70/)).toBeInTheDocument();
    });
  });

  test("falls back to symbol interval endpoint price when quotes are empty", async () => {
    useQuotesMock.mockReturnValue({});
    const fetchImpl = (url, options = {}) => {
      if (url.includes("/api/paper/symbols/AAPL/interval/")) {
        return Promise.resolve(
          mockResponse({
            symbol: "AAPL",
            interval: "1m",
            period: "max",
            last_close: 99.12,
            candles: [],
          })
        );
      }
      return defaultFetchImpl(url, options);
    };

    renderOrders(fetchImpl);

    await screen.findByText("AAPL");

    const symbolInput = screen.getByPlaceholderText(/^Symbol$/i);
    await userEvent.clear(symbolInput);
    await userEvent.type(symbolInput, "AAPL");
    await userEvent.click(screen.getByText(/Set symbol/i));
    await userEvent.click(screen.getByText(/Get 1m price/i));

    await waitFor(() => {
      const card = screen.getByText(/Price & Cost/i).parentElement?.parentElement;
      expect(within(card).getByText(/\$99\.12/)).toBeInTheDocument();
    });
  });

  test("shows live price in the Price & Cost card", async () => {
    renderOrders();

    await screen.findByText("AAPL");
    const symbolInput = screen.getByPlaceholderText(/^Symbol$/i);
    await userEvent.clear(symbolInput);
    await userEvent.type(symbolInput, "AAPL");
    await userEvent.click(screen.getByText(/Set symbol/i));
    await userEvent.click(screen.getByText(/Get 1m price/i));

    await waitFor(() => {
      const card = screen.getByText(/Price & Cost/i).parentElement?.parentElement;
      expect(within(card).getByText(/\$12\.34/)).toBeInTheDocument();
    });
  });

  test("renders TradingView micro view when symbol is entered", async () => {
    renderOrders();

    const symbolInput = screen.getByPlaceholderText(/^Symbol$/i);
    await userEvent.clear(symbolInput);
    await userEvent.type(symbolInput, "MSFT");
    await userEvent.click(screen.getByText(/Set symbol/i));

    await waitFor(() => {
      expect(screen.getByText(/Micro view · MSFT/i)).toBeInTheDocument();
    });
  });
});
