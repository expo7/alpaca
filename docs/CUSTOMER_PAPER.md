# Existing Alpaca customer paper accounts

The `/signals` customer paper panel is **superuser/admin-only** until `CUSTOMER_PAPER_CUSTOMERS_ENABLED=true`. Backend permissions enforce the same restriction; ordinary and staff-only logins cannot access it. Later rollout opens these own-account endpoints without exposing Broker sandbox or shadow controls.

## Demonstration

1. Generate API keys in a **separate Alpaca Paper Trading account**. Internal primary/shadow accounts are refused by verified account ID. Broker sandbox credentials are a different product.
2. Paste the paper pair into **Connect your Alpaca paper account**. The server verifies an ACTIVE account, encrypts credentials, and returns only an account suffix. Failed verification preserves the prior pair. Keys never go into browser storage or API responses.
3. **Inspect account / refresh** retrieves actual balances, options permissions, positions, and open orders. Entries require options level 2, sufficient options buying power, an open regular session, and no existing position/order in that contract.
4. Save trade limits. Defaults are $1,000 per trade and two positions. Each entry is **one long call/put contract**, independent of house quantity. Settings allow $1–$100,000 per trade and 1–10 positions. Same-day expiry contracts are excluded initially.
5. Choose a house-entered signal, **Preview one-contract paper trade**, then **Confirm paper order**. Current quote/limits are revalidated before submission. Alternatively, explicitly consent to **Enable paper mirroring** for future entries. Connecting alone places no orders.
6. Refresh the account/history for actual customer order states, fills, protection, exits, and events. No customer fill is inferred from a house fill.

The Broker Options BETA support ticket #363294 is independent of these Trading API paper accounts; each customer's actual account permissions determine options access.

## Execution behavior

A dedicated Celery queue/worker checks accounts every 15 seconds with two processes. PostgreSQL session advisory locks serialize all web/worker operations for each user account. Customer orders never mutate house/shadow/public trade records.

Mirroring follows only house entries submitted within 120 seconds and after the latest consent. It never backfills historical/missed trades. Customer rollout excludes operator test signals. A unique connection/signal row and stable client order IDs prevent duplicates. Submission intent is committed before HTTP. Timeouts/5xx are reconciled by exact client order ID; missing lookup results never cause another POST. Explicit 429 rejection permits a later attempt after cooldown. Other explicit rejections remain recorded.

Filled entries receive a broker-held stop or target using the house hysteresis policy. Switching confirms cancellation before another sell; a fill racing cancellation closes the row without double selling. Stops tighten without loosening. House closure triggers an independently reconciled customer close. Missing protection after a crossed stop uses a market exit. External quantity changes pause sells; external closes record no invented exit price. Exit rejection/ambiguity produces a staff operations outbox warning and an inspectable error.

Pausing mirroring blocks/cancels new mirror entries while existing positions retain exit management. Manual test orders are independent of the mirror toggle. The global entry switch blocks/cancels entries while preserving reconciliation/exits. Disconnect/replacement is refused while executions remain unresolved; later disconnect clears credentials and retains audit history. A login with trade history must reconnect the same paper account.

## Configuration and rollout

Deployment runs `scripts/configure_customer_paper.py`, which adds absent settings without printing or rotating secrets:

- `CUSTOMER_PAPER_CREDENTIAL_KEY`: random dedicated Fernet key, generated once.
- `CUSTOMER_PAPER_CONNECT_ENABLED=true`: admin connection enabled.
- `CUSTOMER_PAPER_EXECUTION_ENABLED=true`: admin entry capability enabled, subject to a fresh dedicated worker heartbeat, authorization, and limits. Mirroring defaults off.
- `CUSTOMER_PAPER_CUSTOMERS_ENABLED=false`: admin-only visibility/access.

Provisioning atomically writes mode 0600, preserves ownership and existing switch values. Back up the encryption key alongside the encrypted database in an approved secret store. Losing/rotating it without re-encryption requires account reconnection.

To open the paper workflow, set `CUSTOMER_PAPER_CUSTOMERS_ENABLED=true` in the server environment and recreate web, customer worker, and beat. Reload/login to refresh profile visibility. Ordinary users only see their own connection/history. Turning the rollout switch off stops ordinary customers' new entries while ongoing exits remain managed.

Optional OAuth requires approved app configuration (`ALPACA_CONNECT_ENABLED`, client ID/secret, exact callback `https://quantelle.io/api/alpaca-paper/callback/`, and token encryption key). It requests `env=paper` and `scope=trading`; tokens without granted trading scope remain read-only. API-key connection works without OAuth setup. The adapter has no live-money endpoint or rollout flag.

## Shared server and rate limits

Alpaca publishes 200 Trading API requests/minute **per account**: https://alpaca.markets/support/usage-limit-api-calls. No same-IP guarantee is assumed. Distributed budgets allow 80/minute per customer account (fixed-window boundary bursts stay below 200), 12/sec per account, and 300/minute across the customer adapter. Upstream 429 adds bounded Retry-After account/shared cooldown. There are no automatic HTTP retries or IP rotation. House execution retains its own transport; internal account identities are briefly cached for connection checks.

A short-lived shared options-quote cache uses the house market-data client; no per-customer market-data WebSockets are opened. Confirm market-data redistribution/entitlements and OAuth/customer automation approval before broad rollout. This two-worker/shared-budget setup is initial controlled capacity; measure queue delay/provider behavior before expansion. Throttled/missed entries are skipped rather than replayed late.

## Verification

Tests cover permissions, own-account isolation, encryption, exact-paper endpoints, budgets/429 backoff, consent/limits, house-record isolation, options/inventory checks, ambiguous POST recovery, protection, opt-out, cancellation/fill races, and fresh-only mirroring. CI also runs the established house/shadow lifecycle tests and full frontend suite.

A separate customer paper-key verification and controlled customer fill remain necessary to demonstrate the provider flow. Broker fakes do not prove Alpaca acceptance. Deployment adds no customer credentials and opts in no user automatically. Inspect attention/unconfirmed rows at the broker; never remove intent or change a client ID merely to force another submission.
