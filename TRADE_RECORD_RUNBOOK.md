# Quantelle trade record: Monday publishing runbook

## Publish a setup

1. Open `/admin/`, then **Trade signals** → **Add trade signal**.
2. Enter the exact instrument. Options require the option type, strike, and expiration.
3. Enter the planned entry range, initial stop, and up to three targets.
4. Add the underlying trigger, confirmation rule, do-not-chase premium, entry deadline, and official fill method. Use **Ask at activation** unless the spread makes that execution unrealistic.
5. Write the thesis using only information available at publication time. Add the invalidation condition and evidence tags.
6. Save as **Draft** while reviewing it. When ready, change the status to **Published — waiting for entry** and save. The publication timestamp and best-effort delayed quote snapshot are created automatically.
7. Confirm the setup, exact OCC contract symbol, publication snapshot, and current quote appear correctly at `/signals` before sharing it.

Once published, the original plan is locked. Corrections and decisions must be added as new timestamped updates.

## Manage a published setup

- When the entry fills, set the signal to **Open**, record `actual_entry`, and append an **Entry triggered** update.
- When a target is reached, append a **Target reached** update with the price and return at that moment.
- When raising a stop, update `current_stop` and append a **Stop changed** update explaining the change.
- For partial exits, append a **Partial exit** update. Do not mark the signal closed while any portion remains open.
- At the final exit, set the signal to **Closed**, record the final exit, realized return, maximum observed return, and append a **Closed** update.
- If the entry never triggers, use **Cancelled** or **Expired** and explain why in an update.

## Monday pre-publication checklist

- Verify the option symbol, strike, call/put, and expiration against the live chain.
- Verify the generated OCC contract symbol against the brokerage contract.
- Confirm the bid/ask spread and open interest are acceptable.
- Confirm the entry, stop, and targets refer to the option premium—not the underlying share price—or state otherwise in the thesis.
- Make sure the risk label reflects the chance of losing the full premium.
- Recalculate each percentage from the recorded execution price; do not substitute the best intraday price for a realized return.
- Review the public card immediately after publication.
- If the automatic publication quote is unavailable, record that fact rather than reconstructing a favorable historical quote later.

The system is ready to record trades; it does not yet select or execute them automatically.

## Lifecycle certification auditor

The server audits unresolved and recently completed paper-trade lifecycles every two minutes. It also schedules an immediate audit after lifecycle transitions and a final delayed audit two minutes after closure. The auditor is observational: it never places, replaces, cancels, or closes an order and never changes a trade's lifecycle state.

Each report reconciles the Quantelle database, Alpaca paper orders and positions, executor state, Guardian heartbeat/protection, Telegram delivery, and the public record. A trade is certified only after every required checkpoint passes. Disagreements are persisted and create one idempotent operational Telegram warning per signal and discrepancy-code set; retries do not create alert spam.

Retrieve the latest reports through the narrow research-operator credential:

```text
GET /api/operator/lifecycle-certifications/?limit=25
GET /api/operator/lifecycle-certifications/?signal_id=<id>
```

The equivalent read-only server command is:

```bash
python manage.py lifecycle_certification_report --limit 25
```

Operational checks:

- Beat schedule key: `trade-lifecycle-certification-auditor`; interval: 120 seconds.
- Task: `ranker.tasks.run_lifecycle_certification_auditor`.
- A stale/degraded Guardian, broker mismatch, missing Telegram event, duplicate lifecycle artifact, or Alpaca/API failure leaves the lifecycle unchanged and the certification false.
- `pending` is expected for unresolved trades whose future checkpoints have not occurred.
