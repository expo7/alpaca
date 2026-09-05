import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import ArticleNav from "../components/ArticleNav.jsx";

describe("ArticleNav", () => {
  it("provides dashboard and analytics navigation to staff", async () => {
    const onNavigateDashboard = vi.fn();
    const onNavigateAnalytics = vi.fn();
    render(
      <ArticleNav
        isAuthed
        user={{ username: "owner", is_staff: true }}
        onNavigateDashboard={onNavigateDashboard}
        onNavigateAnalytics={onNavigateAnalytics}
        onLogout={() => {}}
      />
    );

    await userEvent.click(screen.getByRole("button", { name: "Dashboard" }));
    await userEvent.click(screen.getByRole("button", { name: "Analytics" }));

    expect(onNavigateDashboard).toHaveBeenCalledOnce();
    expect(onNavigateAnalytics).toHaveBeenCalledOnce();
  });

  it("does not expose analytics navigation to regular readers", () => {
    render(
      <ArticleNav
        isAuthed
        user={{ username: "reader", is_staff: false }}
        onNavigateDashboard={() => {}}
        onNavigateAnalytics={() => {}}
        onLogout={() => {}}
      />
    );

    expect(screen.queryByRole("button", { name: "Analytics" })).not.toBeInTheDocument();
  });
});
