import { render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import useQuotes from "../hooks/useQuotes.js";

function QuotesProbe({ symbols }) {
  const quotes = useQuotes(symbols, { debounceMs: 0, pollMs: 0 });
  return (
    <div>
      {Object.entries(quotes).map(([sym, price]) => (
        <span key={sym}>{`${sym}:${price}`}</span>
      ))}
    </div>
  );
}

const mockResponse = (data, ok = true, status = 200) => ({
  ok,
  status,
  json: async () => data,
});

describe("useQuotes hook", () => {
  test("fetches and returns quote map for symbols", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(mockResponse([{ symbol: "AAPL", price: 123.45 }]))
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<QuotesProbe symbols={["AAPL"]} />);

    await waitFor(() => expect(screen.getByText("AAPL:123.45")).toBeInTheDocument());
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/paper/quotes/?symbols=AAPL")
    );
  });

  test("does nothing when no symbols provided", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    render(<QuotesProbe symbols={[]} />);
    await waitFor(() => expect(fetchMock).not.toHaveBeenCalled());
  });
});
