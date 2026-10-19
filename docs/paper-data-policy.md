# Primary paper experiment data policy

The main published-signal executor prefers a fresh configured underlying feed. If unavailable, it may use Alpaca delayed SIP quotes no older than 20 minutes (15 minute feed delay plus delivery tolerance). Original timestamps and feed names are retained; delayed trigger provenance is included in the entry event. This is approximate delayed observation confirmation, not live confirmation.

This restores the explicitly authorized delayed-data paper experiment. Customer and shadow callers keep strict freshness by default. Option quotes still require the existing freshness and spread checks. Entry limits, deadline, one-contract setup quantity, paper-only endpoint, broker fills and protective exits remain unchanged. No historical record or fill is rewritten.

A published setup is not a fill. IWM signal 16 was published October 15 through operator issue 135; its original same-day deadline must not be silently extended. New sessions require fresh assessment.
