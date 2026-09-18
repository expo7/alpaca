import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import TradeSignalsPage from "../pages/TradeSignalsPage.jsx";

describe("TradeSignalsPage", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("shows the empty state before the first publication", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => [] }));
    render(<TradeSignalsPage />);
    expect(await screen.findByText("No setups published yet")).toBeInTheDocument();
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
    expect(screen.getAllByText("+40.65%")).toHaveLength(2);
    expect(screen.getByText("Booked profits at the second target.")).toBeInTheDocument();
  });

  it("shows a Pro call to action without leaking an active setup", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [{
        id: 2,
        symbol: "NVDA",
        company_name: "NVIDIA Corporation",
        instrument_type: "call",
        status: "published",
        status_label: "Published — waiting for entry",
        risk_level: "high",
        published_at: "2026-09-15T21:36:00Z",
        is_locked: true,
      }],
    }));

    render(<TradeSignalsPage />);
    expect(await screen.findByText("Active NVDA setup")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /View Quantelle Pro/i })).toBeInTheDocument();
    expect(screen.queryByText(/entry range/i)).toBeInTheDocument();
  });

  it("shows unrealized Alpaca paper P/L for an executed open trade", async () => {
    vi.stubGlobal("fetch", vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => [{
        id: 3,
        symbol: "NVDA",
        company_name: "NVIDIA Corporation",
        instrument_type: "call",
        instrument: "NVDA 240C 10/16/26",
        contract_symbol: "NVDA261016C00240000",
        status: "open",
        status_label: "Open",
        risk_level: "high",
        entry_low: "2.90",
        initial_stop: "1.90",
        target_1: "4.25",
        thesis: "Test thesis",
        evidence_tags: [],
        paper_execution_enabled: true,
        paper_quantity: 1,
        published_at: "2026-09-10T13:30:00Z",
        updates: [],
      }] })
      .mockResolvedValueOnce({ ok: true, json: async () => ({
        available: true,
        status_label: "Delayed quote",
        underlying_price: 221.10,
        paper_position: {
          available: true,
          quantity: 1,
          average_entry_price: 2.91,
          current_price: 3.20,
          market_value: 320,
          unrealized_pl: 29,
          unrealized_pl_pct: 9.97,
          fetched_at: "2026-09-17T15:00:00Z",
        },
      }) }));

    render(<TradeSignalsPage token="pro-token" />);
    expect(await screen.findByText("Alpaca paper position")).toBeInTheDocument();
    expect(screen.getByText("$29.00")).toBeInTheDocument();
    expect(screen.getByText("(+9.97%)")).toBeInTheDocument();
  });

  it("separates open positions, pending entries, and completed history", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [
        {
          id: 10,
          symbol: "AMZN",
          company_name: "Amazon",
          instrument_type: "call",
          status: "open",
          status_label: "Open",
          risk_level: "moderate",
          published_at: "2026-09-18T14:00:00Z",
          is_locked: true,
        },
        {
          id: 11,
          symbol: "INTC",
          company_name: "Intel",
          instrument_type: "call",
          status: "published",
          status_label: "Published — waiting for entry",
          risk_level: "high",
          published_at: "2026-09-18T15:00:00Z",
          is_locked: true,
        },
        {
          id: 12,
          symbol: "NVDA",
          company_name: "NVIDIA",
          instrument_type: "call",
          instrument: "NVDA 240C 10/16/26",
          status: "closed",
          status_label: "Closed",
          risk_level: "high",
          entry_low: "2.90",
          initial_stop: "1.90",
          target_1: "4.25",
          thesis: "Completed test trade.",
          evidence_tags: [],
          published_at: "2026-09-10T13:30:00Z",
          updates: [],
          is_locked: false,
        },
      ],
    }));

    render(<TradeSignalsPage />);

    expect(await screen.findByRole("heading", { name: "Open positions" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Pending entries" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Completed history/ })).toBeInTheDocument();
    expect(screen.getByText("3 published · 1 open · 1 pending")).toBeInTheDocument();
    expect(document.getElementById("trade-12")).toBeInTheDocument();
  });

});
