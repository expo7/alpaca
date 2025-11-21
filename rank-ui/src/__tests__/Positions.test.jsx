import { render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import Positions from "../pages/Positions.jsx";
import { AuthProvider } from "../AuthProvider.jsx";

vi.mock("../hooks/useQuotes.js", () => ({
  default: () => ({}),
}));

const mockResponse = (data, ok = true, status = 200) => ({
  ok,
  status,
  json: async () => data,
});

function renderPositions(fetchImpl) {
  vi.stubGlobal("fetch", vi.fn(fetchImpl));
  localStorage.setItem("access", "token");
  return render(
    <AuthProvider>
      <Positions />
    </AuthProvider>
  );
}

describe("Positions page", () => {
  test("renders empty state when no positions", async () => {
    const fetchImpl = (url) => {
      if (url.includes("/api/paper/positions/")) {
        return Promise.resolve(mockResponse({ results: [] }));
      }
      if (url.includes("/api/paper/portfolios/")) {
        return Promise.resolve(mockResponse([{ id: 1, name: "Paper", equity: 10000 }]));
      }
      return Promise.resolve(mockResponse({}));
    };
    renderPositions(fetchImpl);
    await waitFor(() =>
      expect(screen.getByText(/No positions/i)).toBeInTheDocument()
    );
  });

  test("renders populated positions rows", async () => {
    const fetchImpl = (url) => {
      if (url.includes("/api/paper/positions/")) {
        return Promise.resolve(
          mockResponse({
            results: [
              {
                id: 1,
                symbol: "AAPL",
                quantity: 10,
                market_value: 1500,
                portfolio: 1,
                price: 150,
              },
            ],
            count: 1,
            limit: 50,
            next: null,
            previous: null,
          })
        );
      }
      if (url.includes("/api/paper/portfolios/")) {
        return Promise.resolve(mockResponse([{ id: 1, name: "Paper", equity: 10000 }]));
      }
      return Promise.resolve(mockResponse({}));
    };
    renderPositions(fetchImpl);
    await screen.findByText("AAPL");
    expect(screen.getByText(/\$1,500/)).toBeInTheDocument();
  });

  test("shows error when fetch fails", async () => {
    const fetchImpl = (url) => {
      if (url.includes("/api/paper/positions/")) {
        return Promise.resolve(mockResponse({ detail: "fail" }, false, 500));
      }
      if (url.includes("/api/paper/portfolios/")) {
        return Promise.resolve(mockResponse([]));
      }
      return Promise.resolve(mockResponse({}));
    };
    renderPositions(fetchImpl);
    await waitFor(() => expect(screen.getByText(/fail/i)).toBeInTheDocument());
  });
});
