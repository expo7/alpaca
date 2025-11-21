import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import Watchlists from "../pages/Watchlists.jsx";
import { AuthProvider } from "../AuthProvider.jsx";

const mockResponse = (data, ok = true, status = 200) => ({
  ok,
  status,
  json: async () => data,
});

function renderWatchlists(fetchImpl, onUseTickers = vi.fn()) {
  vi.stubGlobal("fetch", vi.fn(fetchImpl));
  localStorage.setItem("access", "token");
  return render(
    <AuthProvider>
      <Watchlists onUseTickers={onUseTickers} />
    </AuthProvider>
  );
}

describe("Watchlists page", () => {
  test("handles empty state and create flow", async () => {
    const fetchImpl = (url, opts = {}) => {
      if (url.includes("/api/watchlists/") && opts.method === "POST") {
        return Promise.resolve(mockResponse({ id: 2, name: "Tech" }));
      }
      if (url.includes("/api/watchlists/")) {
        return Promise.resolve(mockResponse([]));
      }
      return Promise.resolve(mockResponse({}));
    };

    renderWatchlists(fetchImpl);
    await waitFor(() => expect(screen.getAllByText(/Watchlists/i).length).toBeGreaterThan(0));

    await userEvent.type(screen.getByPlaceholderText(/New watchlist name/i), "Tech");
    await userEvent.click(screen.getByRole("button", { name: /Create/i }));
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/watchlists/"),
      expect.objectContaining({ method: "POST" })
    );
  });

  test("renders populated list and allows add/remove symbol", async () => {
    const onUse = vi.fn();
    const fetchImpl = (url, opts = {}) => {
      if (url.includes("/items/") && opts.method === "POST") {
        return Promise.resolve(mockResponse({ id: 10, symbol: "MSFT" }));
      }
      if (url.includes("/items/") && opts.method === "DELETE") {
        return Promise.resolve(mockResponse({}));
      }
      if (url.includes("/api/watchlists/") && !opts.method) {
        return Promise.resolve(
          mockResponse([
            { id: 1, name: "Growth", items: [{ id: 5, symbol: "AAPL" }] },
          ])
        );
      }
      if (url.includes("/api/watchlists/") && opts.method === "DELETE") {
        return Promise.resolve(mockResponse({}));
      }
      return Promise.resolve(mockResponse({}));
    };

    renderWatchlists(fetchImpl, onUse);
    await screen.findByText("Growth");
    await userEvent.click(screen.getByRole("button", { name: /Use in Ranker/i }));
    expect(onUse).toHaveBeenCalledWith(["AAPL"]);

    await userEvent.click(screen.getByRole("button", { name: /\+ Add symbol/i }));
    await userEvent.type(screen.getByPlaceholderText(/e\.g\., AAPL/i), "MSFT");
    await userEvent.click(screen.getByRole("button", { name: /^Add$/i }));
    await waitFor(() => expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/items/"),
      expect.objectContaining({ method: "POST" })
    ));

    await userEvent.click(screen.getByRole("button", { name: /Delete/i }));
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/watchlists/1/"),
      expect.objectContaining({ method: "DELETE" })
    );
  });
});
