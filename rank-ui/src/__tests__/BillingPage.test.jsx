import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import BillingPage from "../pages/BillingPage.jsx";


describe("BillingPage", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("offers sign in to anonymous visitors", () => {
    render(<BillingPage token="" isAuthed={false} />);
    expect(screen.getByText("$49")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /sign in to subscribe/i })).toHaveAttribute("href", "/");
  });

  it("shows checkout for an authenticated non-subscriber", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ configured: true, is_pro: false, status: "inactive" }),
    }));
    render(<BillingPage token="token" isAuthed />);
    expect(await screen.findByRole("button", { name: /subscribe with stripe/i })).toBeEnabled();
  });

  it("shows the customer portal action for Pro", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ configured: true, is_pro: true, status: "active" }),
    }));
    render(<BillingPage token="token" isAuthed />);
    expect(await screen.findByRole("button", { name: /manage subscription/i })).toBeInTheDocument();
  });
});
