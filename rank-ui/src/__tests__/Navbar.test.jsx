import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Navbar from "../components/Navbar.jsx";

describe("Navbar", () => {
  test("renders V1 tabs and fires navigation", async () => {
    const onNavigate = vi.fn();
    render(
      <Navbar
        user={{ username: "tester" }}
        active="dashboard"
        onNavigate={onNavigate}
        onLogout={() => { }}
        v1Mode
      />
    );

    const dashboards = screen.getAllByRole("button", { name: /^Dashboard$/i });
    expect(dashboards.length).toBeGreaterThan(0);
    expect(screen.getAllByRole("button", { name: /Alerts/i }).length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: /Strategies/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Orders/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Leaderboards/i })).not.toBeInTheDocument();

    await userEvent.click(screen.getAllByRole("button", { name: /Alerts/i })[0]);
    expect(onNavigate).toHaveBeenCalledWith("alerts");
  });
});
