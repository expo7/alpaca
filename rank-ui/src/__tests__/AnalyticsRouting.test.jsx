import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "../App.jsx";
import { AuthProvider } from "../AuthProvider.jsx";

const response = (data) => ({ ok: true, status: 200, json: async () => data });

describe("analytics route synchronization", () => {
  beforeEach(() => {
    localStorage.clear();
    localStorage.setItem("access", "staff-token");
    localStorage.setItem("auth_user", JSON.stringify({ username: "owner", is_staff: true }));
    window.history.replaceState({}, "", "/analytics");
    vi.stubGlobal("fetch", vi.fn((url) => {
      if (String(url).includes("/api/auth/me/")) return Promise.resolve(response({ username: "owner", is_staff: true }));
      if (String(url).includes("/api/analytics/summary/")) {
        return Promise.resolve(response({ totals: {}, daily: [], top_pages: [], referrers: [], events: [] }));
      }
      if (String(url).includes("/api/articles/")) return Promise.resolve(response([]));
      if (String(url).includes("/api/macro/dashboard/")) return Promise.resolve(response({ scores: {}, playbook: {} }));
      if (String(url).includes("/api/watchlists/")) return Promise.resolve(response([]));
      return Promise.resolve(response({}));
    }));
  });

  it("returns to the dashboard after visiting articles from analytics", async () => {
    render(<AuthProvider><App /></AuthProvider>);
    expect(await screen.findByText("Site analytics")).toBeInTheDocument();

    await userEvent.click(screen.getAllByRole("button", { name: "Articles" })[0]);
    expect(await screen.findByRole("heading", { name: "Articles" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Dashboard" }));
    expect(await screen.findByText("Stock opportunities")).toBeInTheDocument();
    expect(screen.queryByText("Site analytics")).not.toBeInTheDocument();
  });
});
