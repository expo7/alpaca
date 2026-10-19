import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { vi, describe, it, expect, afterEach } from "vitest";
import OptionStrategies from "../components/OptionStrategies.jsx";

afterEach(() => vi.unstubAllGlobals());
const row = {
  id: 1, symbol: "CLF", kind: "vertical", state: "open", entry_limit: "-0.50", entry_fill: "-0.55",
  legs: [{ symbol: "CLF261120P00010000", side: "buy" }, { symbol: "CLF261120P00012000", side: "sell" }],
  risk: { max_loss_dollars: "150", basis: "Theoretical payoff before fees." },
  quote: {}, events: [], stop_loss_dollars: "75", take_profit_dollars: "25",
  protection: "Monitored exits; no broker-held complex stop", thesis: "A bullish paper idea", invalidation: "Support fails",
};
describe("complex paper records", () => {
  it("shows both short/long legs and distinguishes monitored exits from a broker stop", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ strategies: [row] }) }));
    render(<OptionStrategies />);
    expect(await screen.findByText("CLF · vertical · PAPER #1")).toBeInTheDocument();
    expect(screen.getByText("SELL 1 CLF261120P00012000")).toBeInTheDocument();
    expect(screen.getByText(/no broker-held complex stop/)).toBeInTheDocument();
    expect(screen.getByText(/credit/)).toBeInTheDocument();
  });
  it("keeps a cancelled setup out of completed-trade results", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ strategies: [{ ...row, state: "cancelled" }] }) }));
    render(<OptionStrategies />);
    await waitFor(() => expect(fetch).toHaveBeenCalled());
    fireEvent.click(screen.getByRole("button", { name: "completed" }));
    expect(await screen.findByText("No completed complex strategies recorded.")).toBeInTheDocument();
    expect(screen.queryByText("CLF · vertical · PAPER #1")).not.toBeInTheDocument();
  });
  it("shows a data failure instead of silently reporting no strategies", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));
    render(<OptionStrategies />);
    expect(await screen.findByRole("alert")).toHaveTextContent("unavailable");
  });
});
