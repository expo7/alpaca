import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import Settings from "../pages/Settings.jsx";
import { AuthProvider } from "../AuthProvider.jsx";

const mockResponse = (data, ok = true, status = 200) => ({
  ok,
  status,
  text: async () => JSON.stringify(data),
});

function renderSettings(fetchImpl) {
  vi.stubGlobal("fetch", vi.fn(fetchImpl));
  localStorage.setItem("access", "token");
  return render(
    <AuthProvider>
      <Settings
        tickers="AAPL,MSFT"
        techWeight={0.6}
        fundWeight={0.4}
        ta={{ trend: 0.35, momentum: 0.25, volume: 0.2, volatility: 0.1, meanreversion: 0.1 }}
        setTickers={() => {}}
        setTechWeight={() => {}}
        setFundWeight={() => {}}
        setTa={() => {}}
      />
    </AuthProvider>
  );
}

describe("Settings page", () => {
  test("renders prefs and saves successfully", async () => {
    const fetchImpl = (url, opts = {}) => {
      if (url.includes("/api/user-prefs/") && opts.method === "PATCH") {
        return Promise.resolve(mockResponse({}));
      }
      if (url.includes("/api/user-prefs/")) {
        return Promise.resolve(
          mockResponse({
            daily_scan_enabled: true,
            daily_scan_min_score: 20,
            daily_scan_max_ideas: 5,
          })
        );
      }
      return Promise.resolve(mockResponse({}));
    };

    renderSettings(fetchImpl);

    await screen.findAllByText(/Daily scan email/i);
    await userEvent.click(screen.getByRole("button", { name: /Save email settings/i }));
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/user-prefs/"),
        expect.objectContaining({ method: "PATCH" })
      )
    );
  });

  test("shows error on prefs load failure", async () => {
    renderSettings(() =>
      Promise.resolve(mockResponse({ detail: "bad" }, false, 500))
    );
    await waitFor(() => expect(screen.getByText(/bad/i)).toBeInTheDocument());
  });
});
