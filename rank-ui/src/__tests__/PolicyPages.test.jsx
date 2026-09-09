import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App.jsx";
import { AuthProvider } from "../AuthProvider.jsx";
import PolicyPage from "../pages/PolicyPage.jsx";

describe("public policy pages", () => {
  beforeEach(() => {
    localStorage.clear();
    window.history.replaceState({}, "", "/");
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({ ok: true, json: async () => ({}) })));
  });

  it("renders support contact information", () => {
    render(<PolicyPage type="support" />);
    expect(screen.getByRole("heading", { name: "How can we help?" })).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "support@quantelle.io" })[0]).toHaveAttribute("href", "mailto:support@quantelle.io");
  });

  it("accurately describes first-party analytics", () => {
    render(<PolicyPage type="privacy" />);
    expect(screen.getByRole("heading", { name: "Your privacy at Quantelle" })).toBeInTheDocument();
    expect(screen.getByText(/cryptographically hashing network and browser information/i)).toBeInTheDocument();
    expect(screen.getByText(/respect the browser Do Not Track setting/i)).toBeInTheDocument();
  });

  it("states subscription and investment terms", () => {
    render(<PolicyPage type="terms" />);
    expect(screen.getByRole("heading", { name: "Terms for using Quantelle" })).toBeInTheDocument();
    expect(screen.getByText(/Subscriptions renew automatically until canceled/i)).toBeInTheDocument();
    expect(screen.getByText(/Options can expire worthless/i)).toBeInTheDocument();
  });

  it("makes the privacy URL public without signing in", () => {
    window.history.replaceState({}, "", "/privacy");
    render(<AuthProvider><App /></AuthProvider>);
    expect(screen.getByRole("heading", { name: "Your privacy at Quantelle" })).toBeInTheDocument();
  });
});
