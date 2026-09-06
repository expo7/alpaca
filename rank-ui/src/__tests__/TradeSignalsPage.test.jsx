import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import TradeSignalsPage from "../pages/TradeSignalsPage.jsx";

describe("TradeSignalsPage", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("shows the Monday launch state before the first publication", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => [] }));
    render(<TradeSignalsPage />);
    expect(await screen.findByText("The record starts Monday")).toBeInTheDocument();
  });

  it("shows published plans and completed outcomes", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [{
        id: 1,
        symbol: "MU",
        company_name: "Micron Technology, Inc.",
        instrument_type: "call",
        instrument: "MU 110C 9/18/26",
        status: "closed",
        status_label: "Closed",
        risk_level: "high",
        entry_low: "12.30",
        entry_high: null,
        initial_stop: "9.80",
        target_1: "14.15",
        target_2: "17.30",
        target_3: null,
        thesis: "Momentum and options activity supported the setup.",
        invalidation: "Momentum breaks below support.",
        evidence_tags: ["Price action", "Options flow"],
        published_at: "2026-09-07T14:30:00Z",
        realized_return_pct: "40.65",
        max_return_pct: "48.05",
        updates: [{ id: 1, event_type: "closed", event_label: "Closed", note: "Booked profits at the second target.", occurred_at: "2026-09-07T18:00:00Z" }],
      }],
    }));

    render(<TradeSignalsPage />);
    expect(await screen.findByText("MU 110C 9/18/26")).toBeInTheDocument();
    expect(screen.getByText("+40.65%")).toBeInTheDocument();
    expect(screen.getByText("Booked profits at the second target.")).toBeInTheDocument();
  });
});
