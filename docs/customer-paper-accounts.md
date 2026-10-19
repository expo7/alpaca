# Customer Alpaca paper accounts

Quantelle's own paper account and shadow account remain separate. A customer paper connection is opt-in, read-only at this stage, and cannot place an order. No live Alpaca host is used for account verification or orders.

## Account path

Customers create a paper account directly with Alpaca. Quantelle uses Alpaca Connect OAuth with `env=paper`; Broker API sandbox accounts are for testing a broker integration and are not the customer account path selected here. Alpaca must review the OAuth app, and commercial use must be disclosed in its application.

After app approval, configure `ALPACA_CONNECT_ENABLED=true`, `ALPACA_CONNECT_CLIENT_ID`, `ALPACA_CONNECT_CLIENT_SECRET`, `ALPACA_CONNECT_TOKEN_KEY` (a dedicated Fernet key), and `ALPACA_CONNECT_REDIRECT_URI=https://quantelle.io/api/alpaca-paper/callback/`. Register that exact callback with Alpaca. Keep the values in the server secret store, never in Vite or Git. Do not enable the flag until a real paper account has completed a connection and disconnection test. Rotating the Fernet key requires reauthorizing connected customers or a planned re-encryption migration.

The connect endpoint requires a Quantelle login and uses a short-lived, one-use state. The callback exchanges the code server-side, verifies `/v2/account` only on `paper-api.alpaca.markets`, and stores an encrypted token. The status endpoint returns only the last four characters of the account ID. Disconnect removes the local token; users may also revoke app authorization within Alpaca.

## Execution work still required

The current OAuth request omits the `trading` scope. Both customer modes are **unavailable**. Do not claim Quantelle can execute customer orders until the following are implemented and independently verified:

1. Per-customer consent: either approve an individual setup, or separately enable and later disable future paper setups. Record timestamp, scope, version, and audit history. Never infer consent from merely connecting.
2. Reauthorization with `env=paper` and `trading` scope, then an exact paper-account identity check before every order. Reject any other base URL or account mismatch.
3. Per-user order ledger with unique signal/account/entry and exit intents, stable client order IDs, broker lookup on retry, fill reconciliation, and replay tests. Never duplicate an order after timeout.
4. Per-account limits and checks: one contract maximum by default, options permission and buying power, symbol and entry conditions, current quote freshness, spread, order type, market hours, and missing-data abstention. No automatic order simply because a public signal exists.
5. Manage each customer's actual fills, broker-held protection, cancellations, partial fills, disconnected accounts, user-created positions, and exits independently from Quantelle's public paper record. Do not report a customer result as the public strategy result.
6. Customer-facing activity and failure alerts, emergency pause, authenticated disconnect and disable controls, and policy/consent review before activation.

The existing Quantelle policy says it does not execute subscriber trades. Keep this integration disabled and update the policy only when an execution path is genuinely ready.
