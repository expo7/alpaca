# Complex paper options — operating contract

## Supported structures

One strategy unit; one contract per leg. Standard 100-share US options only, one underlying, two or four distinct legs. Effective Alpaca options level 3 and the exact paper endpoint are checked. All opens/closes use one `order_class: mleg` request, never separate short-leg orders.

- `vertical`: one long/one short, same type/expiry; debit or credit.
- `iron_condor`: ordered long put / short put / short call / long call, same expiry, net credit.
- `straddle` / `strangle`: two long options, same expiry; debit.
- `calendar`: same strike/type, later long against earlier short; debit.
- `diagonal`: same type, later long against earlier short; debit.
- `double_diagonal`: one later long/earlier short pair for each option type; debit.

Naked short options, standalone cash-secured puts, equity assignment management, automatic rolls, ratio spreads, foreign futures options and customer account mirroring are not implemented by this release. Do not approximate these with individual unsupported orders. Preserve the primary QQQ position and its protection.

## Risk and exits

Net entry limits are SIGNED per share: debit positive, credit negative. Broker fill cashflows are reconstructed from every leg's observed fill, not the parent mark or the proposed price. Dollar P/L = (signed liquidation value − signed entry cost) ×100, before fees. Pending, entering, open, closing and closed are distinct; a cancelled setup is not a completed trade.

Same-expiration theoretical risk/profit is evaluated at all strike breakpoints and tails. Time spreads show a conservative debit-plus-strike-gap risk bound and UNKNOWN maximum profit; do not claim an exact expiry payoff or an IV-crush profit from a simple range. American-option assignment, execution and fees can create additional losses. Entry/exit records retain all legs and original risk assumptions.

Complex positions do **not** have a broker-held stop. The existing independent Guardian process monitors net liquidation P/L and submits a whole-strategy market close on the dollar loss/profit threshold, explicit close request or close-by deadline. Contract wings/long premiums bound the theoretical strategy risk while all intended legs remain intact. Exits can slip; monitored thresholds are not guaranteed fills. Single-leg broker-held stops remain unchanged.

`close_by` must precede the earliest option expiration date, and `entry_deadline` must precede close_by. If the broker's next session would miss close_by, close during the final hour of the current session. Early assignment or unexpected leg inventory creates a staff incident and stops automatic orders for that affected strategy; inspect shares/options before recovery. Never sell the protective long alone.

The Guardian manages one strategy per cycle, in oldest-check order, after primary recovery. No extra worker or recurring process. As authorized October 19, primary paper entries have no concurrent trade-count limit; each setup is evaluated independently. The legacy ALPACA_PAPER_MAX_OPEN_POSITIONS environment value is ignored and diagnostics report null (unlimited). A DB reservation lock still serializes primary/complex entries. Contracts cannot overlap another active primary or complex record. Broker buying power, quote validation and lifecycle controls still apply. Customer and shadow account limits are unchanged. Failed complex monitoring cannot interrupt primary exits. A stale management timestamp is visible; more active strategies lengthen the oldest-check rotation.

## Operator actions

Owner GitHub issue title starts `[Quantelle Operator] Strategy`. Body is strict JSON.

Publication/preview fields (all required):

```json
{
  "action": "strategy_preview",
  "kind": "vertical",
  "legs": [
    {"symbol": "CLF261120C00014000", "side": "buy"},
    {"symbol": "CLF261120C00016000", "side": "sell"}
  ],
  "entry_limit": "1.00",
  "stop_loss_dollars": "50.00",
  "take_profit_dollars": "50.00",
  "entry_deadline": "2026-10-19T19:30:00Z",
  "close_by": "2026-11-18T19:00:00Z",
  "thesis": "Explain the actually researched current idea and countercase.",
  "invalidation": "Explain what defeats the thesis, independently of the monitored dollar stop."
}
```

This is a schema example, not an approved trade or assertion of current prices. Use `strategy_preview` for fresh quotes/permission/risk verification with zero persisted setups and zero orders. `strategy_publish` creates the immutable pending record and authorizes the existing Guardian to enter when its net limit is available. The workflow derives request_id from the issue; omit it from issue JSON. A preview response and an accepted publication are not fills.

Close/cancel/recovery: `{ "action": "strategy_close", "strategy_id": 1, "note": "At least twenty characters explaining the decision" }`. `strategy_cancel` only applies to unfilled setups; entry-order cancellation must be confirmed before certifying cancellation. `strategy_retry` is explicit recovery of an uncertain submission using the same deterministic client ID; inspect broker inventory/order history first. A rejected terminal entry must be cancelled and newly assessed, not silently recreated. Closing orders only advance their client-ID generation after a terminal zero-fill rejection/cancellation. Partial fills require reconciliation.

Reads: public `/api/option-strategies/`; authenticated operator GET `/api/operator/option-strategies/`; read-only `python manage.py option_strategy_preflight`. On-demand `[Quantelle Data] Probe` includes exact complex records, errors, order IDs and event delivery when installed. Public cards show all legs, source/as-of, fill, risk, deadline, monitoring status and real completed P/L separately from single-leg results. Only publication/fill/close/cancellation notifications go to customers; internal incidents use staff alerts.

## Verification

Test both cashflow signs, payoff bounds, shape validation, permissions, stale quotes, contract collisions, capacity, idempotent submissions, uncertain outcomes, actual per-leg fills, partial/terminal orders, assignment mismatches, deadline exits without quotes, and whole-position closing. Run the existing primary lifecycle suites as regressions. Production verification must distinguish installed capability/preview from the first actual complex fill and eventual close; do not create a dummy trade merely to turn checks green.

References: https://docs.alpaca.markets/us/docs/options-level-3-trading and https://docs.alpaca.markets/us/reference/postorder (verified October19,2026).
