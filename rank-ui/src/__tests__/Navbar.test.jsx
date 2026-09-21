import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Navbar from "../components/Navbar.jsx";

describe("Navbar", () => {
  test("renders V1 tabs and fires navigation from the collapsed menu", async () => {
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

    const user = userEvent.setup();
    const menuButton = screen.getByRole("button", { name: /open navigation menu/i });
    expect(menuButton).toHaveAttribute("aria-expanded", "false");

    await user.click(menuButton);
    const menu = screen.getByRole("navigation", { name: /navigation menu/i });
    expect(within(menu).getByRole("button", { name: /^Today$/i })).toBeInTheDocument();
    expect(within(menu).getByRole("button", { name: /^Live Options$/i })).toBeInTheDocument();
    expect(within(menu).queryByRole("button", { name: /Alerts/i })).not.toBeInTheDocument();
    expect(within(menu).queryByRole("button", { name: /Strategies/i })).not.toBeInTheDocument();

    await user.click(within(menu).getByRole("button", { name: /^Live Options$/i }));
    expect(onNavigate).toHaveBeenCalledWith("signals");
    expect(menuButton).toHaveAttribute("aria-expanded", "false");
  });

  test("preserves the authentication controls and staff-only Analytics visibility", async () => {
    const user = userEvent.setup();
    const onLogout = vi.fn();
    render(
      <Navbar
        isAuthed
        user={{ username: "owner", is_staff: true }}
        active="dashboard"
        onNavigate={() => {}}
        onLogout={onLogout}
        v1Mode
      />
    );

    await user.click(screen.getByRole("button", { name: /open navigation menu/i }));
    expect(
      within(screen.getByRole("navigation", { name: /navigation menu/i })).getByRole(
        "button",
        { name: /^Analytics$/i }
      )
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /^Log out$/i }));
    expect(onLogout).toHaveBeenCalledOnce();
  });
});
