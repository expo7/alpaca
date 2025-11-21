import { render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import Leaderboards from "../pages/Leaderboards.jsx";
import { AuthProvider } from "../AuthProvider.jsx";

const mockResponse = (data, ok = true, status = 200) => ({
  ok,
  status,
  json: async () => data,
});

const seasons = [{ id: 7, name: "Spring" }];
const entries = [
  {
    id: 1,
    rank: 1,
    portfolio: { name: "Portfolio One", base_currency: "USD" },
    metric: "return_pct",
    value: 12.5,
    period: "7d",
    season: 7,
    calculated_at: "2024-01-01T00:00:00Z",
  },
  {
    id: 2,
    rank: 2,
    portfolio: { name: "Portfolio Two", base_currency: "USD" },
    metric: "return_pct",
    value: 5.25,
    period: "7d",
    season: 7,
    calculated_at: "2024-01-02T00:00:00Z",
  },
];

function renderLeaderboards(fetchImpl) {
  vi.stubGlobal("fetch", vi.fn(fetchImpl));
  localStorage.setItem("access", "token");
  return render(
    <AuthProvider>
      <Leaderboards />
    </AuthProvider>
  );
}

describe("Leaderboards", () => {
  test("renders entries with ranks and metrics", async () => {
    const fetchImpl = (url) => {
      if (url.includes("/api/paper/leaderboards/seasons/")) {
        return Promise.resolve(mockResponse(seasons));
      }
      if (url.includes("/api/paper/leaderboards/entries/")) {
        return Promise.resolve(mockResponse(entries));
      }
      return Promise.resolve(mockResponse({}));
    };

    renderLeaderboards(fetchImpl);

    await waitFor(() => expect(screen.getByText("Portfolio One")).toBeInTheDocument());
    const rows = screen.getAllByRole("row");
    expect(rows[1]).toHaveTextContent("1");
    expect(rows[1]).toHaveTextContent("Portfolio One");
    expect(screen.getByText(/12\.50/)).toBeInTheDocument();
    expect(screen.getByText(/Portfolio Two/)).toBeInTheDocument();
  });
});
