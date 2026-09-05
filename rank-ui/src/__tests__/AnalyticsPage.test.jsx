import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AnalyticsPage from "../pages/AnalyticsPage.jsx";

describe("AnalyticsPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("shows the private report to staff", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        totals: { visitors: 4, page_views: 9, article_views: 3, ranking_runs: 2, registrations: 1 },
        daily: [{ date: "2026-09-05", page_views: 9, visitors: 4 }],
        top_pages: [{ path: "/dashboard", views: 5, visitors: 3 }],
        referrers: [{ referrer_host: "www.google.com", views: 2, visitors: 1 }],
        events: [{ event_name: "ranking_run", count: 2, visitors: 1 }],
      }),
    }));

    render(<AnalyticsPage token="token" isStaff />);

    expect(await screen.findByText("Site analytics")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("www.google.com")).toBeInTheDocument());
    expect(screen.getAllByText("Ranking runs")).toHaveLength(2);
  });

  it("does not expose reports to non-staff users", () => {
    render(<AnalyticsPage token="token" isStaff={false} />);
    expect(screen.getByText("Analytics is private")).toBeInTheDocument();
  });
});
