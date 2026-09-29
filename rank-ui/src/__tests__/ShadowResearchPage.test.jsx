import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import ShadowResearchPage from "../pages/ShadowResearchPage.jsx";

afterEach(() => vi.unstubAllGlobals());
const report = { summary: { count: 0, groups: {}, executor_health: { status: "disabled" } }, results: [], count: 0 };
const response = data => ({ ok: true, json: async () => data });
describe("staff shadow research", () => {
  it("does not request private data for a nonstaff user", () => {
    const fetch = vi.fn(); vi.stubGlobal("fetch", fetch);
    render(<ShadowResearchPage token="reader" isStaff={false} />);
    expect(screen.getByText("Shadow research is private")).toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
  });
  it("shows an honest empty state and unavailable inventory, with authenticated filters", async () => {
    const fetch = vi.fn(url => Promise.resolve(response(String(url).includes("account/") ? { status: "unavailable" } : report)));
    vi.stubGlobal("fetch", fetch);
    render(<ShadowResearchPage token="staff" isStaff />);
    expect(await screen.findByText("Waiting for the first prospective setup")).toBeInTheDocument();
    expect(screen.getByText("Unknown")).toBeInTheDocument();
    expect(screen.queryByText("0.00%")).not.toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("Result mode"), "broker_intended");
    await waitFor(() => expect(fetch).toHaveBeenCalledWith(expect.stringContaining("mode=broker_intended"), expect.objectContaining({ headers: { Authorization: "Bearer staff" } })));
  });
  it("labels modeled losses and shows immutable reasoning and events", async () => {
    vi.stubGlobal("fetch", vi.fn(url => Promise.resolve(response(String(url).includes("account/") ? { status: "unavailable" } : { ...report,
      summary: { ...report.summary, count: 1 }, results: [{ id: 1, execution_mode: "observation", status: "completed", rejection_reason: "wide_spread", decision: { symbol: "SPY", thesis: "Original thesis", option_symbol: "SPY-contract", entry_low: "5", entry_high: "6" }, result: { realized_return_pct: "-20" }, event_count: 1, events: [{ kind: "correction", details: { reason: "Preserved correction" } }] }] }))));
    render(<ShadowResearchPage token="staff" isStaff />);
    expect(await screen.findByText("Modeled observation")).toBeInTheDocument();
    expect(screen.getByText("-20.00%")).toBeInTheDocument();
    expect(screen.getAllByText("Original thesis")[0]).toBeVisible();
    await userEvent.click(screen.getByText("Event history · 1"));
    expect(screen.getByText("Preserved correction")).toBeVisible();
  });
});
