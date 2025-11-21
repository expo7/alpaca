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

describe("Flow: Watchlist management", () => {
  test("user adds and removes symbols in a watchlist", async () => {
    let lists = [
      {
        id: 1,
        name: "Tech",
        items: [{ id: 10, symbol: "MSFT" }],
      },
    ];

    const fetchImpl = vi.fn((url, options = {}) => {
      const u = String(url);
      if (u.includes("/api/watchlists/") && (!options.method || options.method === "GET")) {
        return Promise.resolve(mockResponse(lists));
      }
      if (u.includes("/api/watchlists/") && options.method === "POST" && !u.includes("/items/")) {
        // create list
        lists = [...lists, { id: 2, name: "New", items: [] }];
        return Promise.resolve(mockResponse({ id: 2 }));
      }
      if (u.includes("/api/watchlists/1/items/") && options.method === "POST") {
        lists = [
          {
            id: 1,
            name: "Tech",
            items: [...lists[0].items, { id: 11, symbol: "AAPL" }],
          },
        ];
        return Promise.resolve(mockResponse({ id: 11 }));
      }
      if (u.includes("/api/watchlists/1/items/10/") && options.method === "DELETE") {
        lists = [
          {
            id: 1,
            name: "Tech",
            items: lists[0].items.filter((it) => it.id !== 10),
          },
        ];
        return Promise.resolve(mockResponse({}));
      }
      if (u.includes("/api/watchlists/1/items/11/") && options.method === "DELETE") {
        lists = [
          {
            id: 1,
            name: "Tech",
            items: lists[0].items.filter((it) => it.id !== 11),
          },
        ];
        return Promise.resolve(mockResponse({}));
      }
      if (u.includes("/api/watchlists/") && options.method === "DELETE") {
        lists = [];
        return Promise.resolve(mockResponse({}));
      }
      return Promise.resolve(mockResponse([]));
    });

    vi.stubGlobal("fetch", fetchImpl);
    localStorage.setItem("access", "token");
    localStorage.setItem("username", "tester");

    render(
      <AuthProvider>
        <Watchlists />
      </AuthProvider>
    );

    await screen.findByText("Tech");
    expect(screen.getByText("MSFT")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /\+ Add symbol/i }));
    await userEvent.type(screen.getByPlaceholderText(/e\.g\., AAPL/i), "AAPL");
    await userEvent.click(screen.getByRole("button", { name: /^Add$/i }));

    await waitFor(() => expect(fetchImpl).toHaveBeenCalledWith(
      expect.stringContaining("/api/watchlists/1/items/"),
      expect.objectContaining({ method: "POST", body: expect.stringContaining("AAPL") })
    ));
    await waitFor(() => expect(screen.getByText("AAPL")).toBeInTheDocument());

    // remove MSFT
    const removeBtns = screen.getAllByTitle("Remove");
    await userEvent.click(removeBtns[0]); // first symbol (MSFT)
    await waitFor(() =>
      expect(fetchImpl).toHaveBeenCalledWith(
        expect.stringContaining("/api/watchlists/1/items/10/"),
        expect.objectContaining({ method: "DELETE" })
      )
    );
    await waitFor(() => expect(screen.queryByText("MSFT")).not.toBeInTheDocument());
  });
});
