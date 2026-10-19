import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import CustomerPaperPanel from "../components/CustomerPaperPanel.jsx";

const initial = { available: true, connected: false, execution_enabled: true, customer_rollout: false, max_trade_notional: "1000", max_open_positions: 2 };
const linked = { ...initial, connected: true, trading_authorized: true, account_suffix: "1234", mirror_enabled: false };
const ok = data => ({ ok: true, status: 200, json: async () => data });
afterEach(() => vi.unstubAllGlobals());

describe("customer paper connection", () => {
  it("clears entered secrets and shows a verified account without storing keys in browser storage", async () => {
    const fetch = vi.fn((url, opts) => {
      if (opts.method === "POST") return Promise.resolve(ok(linked));
      if (url.endsWith("executions/")) return Promise.resolve(ok({ executions: [], events: [] }));
      if (url.endsWith("account/")) return Promise.resolve(ok({ account: { status: "ACTIVE", cash: "25000", options_trading_level: 2 }, positions: [], orders: [], checked_at: "2026-09-29T15:00:00Z" }));
      return Promise.resolve(ok(fetch.mock.calls.length > 1 ? linked : initial));
    });
    vi.stubGlobal("fetch", fetch);
    render(<CustomerPaperPanel token="admin" />);
    const key = await screen.findByLabelText("Paper API key");
    await userEvent.type(key, "paper-api-key");
    await userEvent.type(screen.getByLabelText("Paper API secret"), "paper-api-secret");
    await userEvent.click(screen.getByText("Verify and save paper account"));
    expect(await screen.findByText("Paper account ending 1234")).toBeVisible();
    expect(screen.queryByText("paper-api-secret")).not.toBeInTheDocument();
    expect(screen.getByText(/Options level 2/)).toBeVisible();
    expect(fetch).toHaveBeenCalledWith(expect.stringContaining("connection/"), expect.objectContaining({ method: "POST", headers: expect.objectContaining({ Authorization: "Bearer admin" }) }));
  });

  it("requires consent before enabling mirrors and uses a distinct preview/confirmation step", async () => {
    const fetch = vi.fn((url, opts) => {
      if (opts.method === "PATCH") return Promise.resolve(ok({ ...linked, mirror_enabled: true }));
      if (opts.method === "POST") return Promise.resolve(ok({ symbol: "QQQ-contract", limit_price: "7", estimated_cost: "700", stop: "4", target: "12" }));
      return Promise.resolve(ok(linked));
    });
    vi.stubGlobal("fetch", fetch);
    render(<CustomerPaperPanel token="admin" signals={[{ id: 7, symbol: "QQQ", instrument_type: "call", status: "open" }]} />);
    const enable = await screen.findByText("Enable paper mirroring");
    expect(enable).toBeDisabled();
    await userEvent.click(screen.getByRole("checkbox"));
    await userEvent.click(enable);
    await screen.findByText("Pause new mirror entries");
    await userEvent.selectOptions(screen.getByLabelText("Paper trade signal"), "7");
    await userEvent.click(screen.getByText("Preview one-contract paper trade"));
    expect(await screen.findByText("Confirm paper order")).toBeVisible();
    const posts = fetch.mock.calls.filter(([,opts]) => opts.method === "POST");
    expect(posts).toHaveLength(1);
    expect(JSON.parse(posts[0][1].body)).toEqual({ signal_id: 7, action: "preview" });
  });

  it("removes old balances when refresh fails", async () => {
    let fail = false;
    vi.stubGlobal("fetch", vi.fn(url => {
      if (url.endsWith("executions/")) return Promise.resolve(ok({ executions: [], events: [] }));
      if (url.endsWith("account/")) return Promise.resolve(fail ? { ok: false, status: 400, json: async () => ({ detail: "Broker unavailable" }) } : ok({ account: { cash: "12345" }, positions: [], orders: [], checked_at: "2026-09-29T15:00:00Z" }));
      return Promise.resolve(ok(linked));
    }));
    render(<CustomerPaperPanel token="admin" />);
    await userEvent.click(await screen.findByText("Inspect account / refresh"));
    expect(await screen.findByText(/Cash \$12,345/)).toBeVisible();
    fail = true;
    await userEvent.click(screen.getByText("Inspect account / refresh"));
    await waitFor(() => expect(screen.queryByText(/Cash \$12,345/)).not.toBeInTheDocument());
    expect(await screen.findByRole("alert")).toHaveTextContent("Broker unavailable");
  });
});
