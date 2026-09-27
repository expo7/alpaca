# Quantelle × Alpaca: admin review build

**Status, September 27, 2026:** A private, staff-only paper connection prototype. No customer order placement or live-money authority. This document describes proposed capabilities for business and legal review; it does not assert regulatory approval.

## Product choices

| Route | Customer journey | Current state | Questions for Alpaca and counsel |
| --- | --- | --- | --- |
| Connect OAuth | Existing Alpaca user authorizes Quantelle; Alpaca hosts login and consent. | Paper-only, read-only OAuth code deployed, feature flag off. Staff-only API/UI in this draft. | Commercial app approval; paper and eventual live scope review; investment-advice/automation classification; disclosures and records. |
| Broker API | Customer starts in Quantelle; Alpaca is account infrastructure. | No integration. Free sandbox is available, but that is not a launched customer product. | Does Alpaca permit persistent, customer-facing **paper-only** accounts under a partner arrangement? Options availability, KYC/agreements, operating obligations, fees and minimums, and future live launch. |
| Quantelle simulated ledger | Customer signs up solely with Quantelle; simulated fills are computed in our own ledger. | Existing general paper features are not a per-customer options-copy system. | How to describe simulations and performance; data licensing and disclosures; whether later migration to Alpaca accounts is practical. |

## Proposed architecture

- One Quantelle identity may have separate provider account links. A link records provider, environment (paper or live), immutable provider account ID, consent scope/version, token reference, status, and timestamps. Do not recycle the house or shadow account for customer activity.
- Provider adapters keep Connect's user-granted OAuth token separate from Broker API's partner credentials. Sandbox, retail paper, and live endpoints have independent configuration and database namespaces. Live credentials cannot be selected through a paper request.
- An order intent belongs to one user, one provider account, one published setup, one action, and one unique client order ID. Store the proposed terms and user approval before network submission. Retries first reconcile the broker by client order ID; an ambiguous timeout must halt, not create a second order.
- Execution must check actual account identity, authorization, options permission, buying power, position/order inventory, market session, fresh quotes, spread, current entry conditions, quantity and duplicate intent. Customer fills, stops, targets, cancellations, and broker protection belong to a separate customer ledger; public Quantelle results remain independent.
- Offer explicit per-trade approval first. A future standing-authorization mode needs its own separate consent and revoke control, limits, audit trail, alerts, and legal review.
- Staff can inspect and test in a private review area. A production release needs backend staff permission on every endpoint, not just a hidden frontend panel. Live trading stays behind a separate deployment and business-approval gate; paper approval must never enable it.

## Review questions for Tommy and counsel

1. What is Quantelle's legal role when it publishes specific options setups, offers one-click execution, or automatically mirrors a setup into a customer's account? How does compensation or discretion change that analysis?
2. Which entity should contract with Alpaca and customers? Which registrations, supervision, advertising/performance rules, options disclosures, records, and customer agreements apply before paper and live launch?
3. What must the customer affirm for each order versus a standing mandate? What revocation, cancellation, incident and complaint process is required?
4. Can the Broker API partner arrangement support a customer-facing paper-only service? If not, should initial accounts use Connect, or should Quantelle maintain its own clearly labeled simulation?
5. What review/approval steps, options enablement, pricing, and operational responsibilities apply to a later live-money rollout?

## Current technical gate

`ALPACA_CONNECT_ENABLED` remains off until an Alpaca-approved commercial OAuth app, server-only credentials, exact callback registration, and a real staff paper connect/disconnect test. The current OAuth request deliberately omits `trading`, so it cannot submit orders. No customer or staff trading endpoint is present in this draft. Do not infer execution permission from a connected account.

The admin-only review panel is intentionally sparse. Next engineering milestones are a consent/order-intent ledger, paper-only adapter, idempotent order and fill reconciliation, independent exit protection, and end-to-end paper tests before switching on submission. A later live route requires separate review and authorization.
