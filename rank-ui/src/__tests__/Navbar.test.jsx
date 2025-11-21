import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Navbar from "../components/Navbar.jsx";

describe("Navbar", () => {
  test("renders tabs and fires navigation", async () => {
    const onNavigate = vi.fn();
    render(
      <Navbar
        user={{ username: "tester" }}
        active="dashboard"
        onNavigate={onNavigate}
        onLogout={() => {}}
      />
    );

    const dashboards = screen.getAllByRole("button", { name: /^Dashboard$/i });
    expect(dashboards.length).toBeGreaterThan(0);
    expect(screen.getAllByRole("button", { name: /Strategies/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("button", { name: /Orders/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("button", { name: /Leaderboards/i }).length).toBeGreaterThan(0);

    await userEvent.click(screen.getAllByRole("button", { name: /Orders/i })[0]);
    expect(onNavigate).toHaveBeenCalledWith("orders");

    await userEvent.click(screen.getAllByRole("button", { name: /Strategies/i })[0]);
    expect(onNavigate).toHaveBeenCalledWith("strategies");
  });
});
