import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import TradeSignalsPage from "../pages/TradeSignalsPage.jsx";

describe("TradeSignalsPage", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("keeps staff incidents out of the latest customer update and folds an open entry plan", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => [{
      id: 88, symbol: "QCOM", instrument: "QCOM call", status: "open", status_label: "Open",
      risk_level: "moderate", instrument_type: "call", entry_low: "8.00", initial_stop: "6.25",
      current_stop: "6.25", target_1: "12.00", actual_entry: "8.50", protection: { type: "broker_stop", price: "6.25" },
      underlying_trigger_price: "150.00", trigger_direction: "above", trigger_confirmation: "Two five minute closes",
      do_not_chase_price: "9.00", entry_deadline: "2026-09-25", thesis: "Breakout thesis",
      published_at: "2026-09-22T14:00:00Z", updates: [
        { id: 1, audience: "customer", note: "Entry filled.", occurred_at: "2026-09-22T15:00:00Z" },
        { id: 2, audience: "staff", note: "Guardian DNS diagnostic", occurred_at: "2026-09-22T16:00:00Z" },
      ],
    }] }));
    render(<TradeSignalsPage />);
    expect(await screen.findByText("Entry filled.")).toBeInTheDocument();
    expect(screen.queryByText("Guardian DNS diagnostic")).not.toBeInTheDocument();
    expect(screen.getByText("Original entry plan")).toBeInTheDocument();
    expect(screen.getByText("Stop $6.25")).toBeInTheDocument();
  });

  it("shows newer verified protection above an earlier customer warning without hiding the history", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => [{
      id: 10, symbol: "QCOM", instrument: "QCOM call", status: "open", status_label: "Open",
      instrument_type: "call", entry_low: "8.00", initial_stop: "6.25", current_stop: "6.25",
      target_1: "14.00", actual_entry: "8.85", thesis: "Breakout thesis",
      published_at: "2026-09-21T16:14:00Z",
      protection: { type: "broker_stop", price: "6.25", verified: true, verified_at: "2026-09-24T19:21:00Z" },
      updates: [{ id: 1, event_type: "execution_warning", audience: "customer",
        note: "Alpaca rejected broker-held OCO protection; Quantelle switched to monitored exits.",
        occurred_at: "2026-09-21T16:16:00Z" }],
    }] }));
    render(<TradeSignalsPage />);
    expect(await screen.findByText("Verified broker protection")).toBeInTheDocument();
    expect(screen.getByText("Stop $6.25")).toBeInTheDocument();
    expect(screen.getByText(/Checked Sep 24, 2026/)).toBeInTheDocument();
    expect(screen.getByText(/Earlier trade update/)).toBeInTheDocument();
    expect(screen.getByText(/Alpaca rejected broker-held OCO protection/)).toBeInTheDocument();
  });

  it("shows the empty state before the first publication", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => [] }));
    render(<TradeSignalsPage />);
    expect(await screen.findByText("No setups published yet")).toBeInTheDocument();
  });

  it("starts on waiting when no position is open", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => [{
      id: 9, symbol: "MU", instrument: "MU call", status: "published", status_label: "Waiting",
      entry_low: "2.00", initial_stop: "1.00", target_1: "3.00", thesis: "Waiting", updates: [],
    }] }));
    render(<TradeSignalsPage />);
    expect(await screen.findByRole("heading", { name: "Pending entries" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Waiting 1/i })).toHaveAttribute("aria-pressed", "true");
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
    expect(screen.getByText("Realized return")).toBeInTheDocument();
    expect(screen.queryByText("+48.05%")).not.toBeInTheDocument();
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
        status_label: "Market closed · last available",
        underlying_price: 221.10,
        option_bid: null,
        option_ask: null,
        option_midpoint: 3.20,
        option_price_label: "Alpaca position mark",
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
    expect(screen.getByText("Alpaca position mark")).toBeInTheDocument();
    expect(screen.getAllByText("— / —").length).toBeGreaterThan(0);
  });

  it("separates filled completed trades from cancelled and expired setups", async () => {
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
          actual_entry: "2.90",
          final_exit: "3.95",
          realized_return_pct: "36.21",
          thesis: "Completed test trade.",
          evidence_tags: [],
          published_at: "2026-09-10T13:30:00Z",
          updates: [],
          is_locked: false,
        },
        { id: 13, symbol: "SHOP", instrument: "SHOP call", status: "cancelled", status_label: "Cancelled", entry_low: "2.00", initial_stop: "1.00", target_1: "3.00", thesis: "Unfilled", updates: [] },
        { id: 14, symbol: "MU", instrument: "MU call", status: "expired", status_label: "Expired", entry_low: "2.00", initial_stop: "1.00", target_1: "3.00", thesis: "Unfilled", updates: [] },
      ],
    }));

    render(<TradeSignalsPage />);

    expect(await screen.findByRole("heading", { name: "Open positions" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Active 1/i })).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(screen.getByRole("button", { name: /All setups 5/i }));
    expect(screen.getByRole("heading", { name: "Pending entries" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Completed trades/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Unfilled and other outcomes/ })).toBeInTheDocument();
    expect(screen.getByText("5 published · 1 active · 1 waiting · 1 completed trades · 2 unfilled/other")).toBeInTheDocument();
    expect(document.getElementById("trade-12")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Waiting 1/i }));
    expect(screen.getByRole("heading", { name: "Pending entries" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Open positions" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Completed trades 1/i }));
    expect(screen.getByRole("heading", { name: /Completed trades/ })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Pending entries" })).not.toBeInTheDocument();
    expect(screen.queryByText("SHOP call")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Unfilled \/ other 2/i }));
    expect(screen.getByText("SHOP call")).toBeInTheDocument();
    expect(screen.getByText("MU call")).toBeInTheDocument();
    expect(screen.queryByText("NVDA 240C 10/16/26")).not.toBeInTheDocument();
  });

  it("shows recorded customer activity, evidence, and a losing gross paper result without staff incidents", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => [{
      id: 7, symbol: "AMZN", instrument: "AMZN call", status: "closed", status_label: "Closed",
      instrument_type: "call", risk_level: "high", entry_low: "15.60", initial_stop: "11.50", target_1: "22.00",
      actual_entry: "15.60", final_exit: "11.50", realized_return_pct: "-26.28", max_return_pct: "8.00",
      paper_execution_enabled: true, paper_quantity: 1, paper_exit_reason: "broker_stop",
      evidence_tags: ["Price action", "Options flow"], thesis: "Published thesis", published_at: "2026-09-17T19:41:00Z",
      updates: [
        { id: 1, event_type: "triggered", event_label: "Entry filled", audience: "customer", note: "Paper entry filled.", occurred_at: "2026-09-18T13:33:00Z" },
        { id: 2, event_type: "execution_warning", audience: "staff", note: "Guardian DNS diagnostic", occurred_at: "2026-09-23T13:00:00Z" },
        { id: 3, event_type: "closed", event_label: "Closed", audience: "customer", note: "Broker stop filled.", occurred_at: "2026-09-24T13:49:00Z" },
      ],
    }] }));
    render(<TradeSignalsPage />);
    expect(await screen.findByText("AMZN call")).toBeInTheDocument();
    expect(screen.getByText("Realized paper return")).toBeInTheDocument();
    expect(screen.getAllByText("-26.28%")).toHaveLength(2);
    expect(screen.getByText("−$410.00")).toBeInTheDocument();
    expect(screen.getByText("Technical confirmation")).toHaveAttribute("title", "Published price-action evidence");
    expect(screen.getByText("Options flow")).toBeInTheDocument();
    expect(screen.getByText(/Exit: broker stop/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /All activity 2/i }));
    const stream = screen.getByRole("heading", { name: "Customer trade activity" }).parentElement;
    expect(within(stream).getByText("Paper entry filled.")).toBeInTheDocument();
    expect(within(stream).getByText("Broker stop filled.")).toBeInTheDocument();
    expect(within(stream).queryByText("Guardian DNS diagnostic")).not.toBeInTheDocument();
    expect(within(stream).getAllByText(/MST/)).toHaveLength(2);
  });

  it("counts the three filled exits as two wins and one loss without counting unfilled plans", async () => {
    const trade = (id, symbol, result) => ({ id, symbol, instrument: `${symbol} call`, status: "closed", status_label: "Closed",
      instrument_type: "call", entry_low: "1.00", initial_stop: "0.50", target_1: "2.00", actual_entry: "1.00",
      final_exit: result > 0 ? "1.50" : "0.75", realized_return_pct: String(result), thesis: "Recorded trade", updates: [] });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => [
      trade(10, "QCOM", 58.76), trade(7, "AMZN", -26.28), trade(6, "NVDA", 36.43),
      { id: 11, symbol: "SHOP", instrument: "SHOP call", status: "cancelled", status_label: "Cancelled",
        entry_low: "1.00", initial_stop: "0.50", target_1: "2.00", thesis: "No fill", updates: [] },
    ] }));
    render(<TradeSignalsPage />);
    expect(await screen.findByText("4 published · 0 active · 0 waiting · 3 completed trades · 1 unfilled/other")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Completed trades 3/i })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText(/2 wins · 1 loss/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Completed trades 3/i }));
    expect(screen.getByText("QCOM call")).toBeInTheDocument();
    expect(screen.getByText("AMZN call")).toBeInTheDocument();
    expect(screen.getByText("NVDA call")).toBeInTheDocument();
    expect(screen.queryByText("SHOP call")).not.toBeInTheDocument();
  });

});
