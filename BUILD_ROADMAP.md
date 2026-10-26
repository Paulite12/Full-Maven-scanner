# Full Maven Scanner — build status and roadmap

## Included in this package

- FastAPI backend and responsive mobile dashboard.
- Dashboard pages for overview, early activity, momentum, risk watch, newly observed symbols, news, saved observations, and system status.
- Public Bybit spot and USDT linear ticker discovery for top-turnover USDT pairs.
- 5-minute candle analysis, relative turnover heuristic, short-term price change, explainable rule score, and risk flags.
- MEXC spot ticker watchlist as secondary intelligence.
- Optional RSS/Atom news ingestion with source coverage status.
- SQLite storage by default; optional PostgreSQL via `DATABASE_URL`.
- Optional Telegram alerts.
- API endpoints for status, market rows, candidates, news, history, and configuration.
- Optional offline baseline training script for user-provided labelled data.
- Local unit tests and Render configuration template.

## Not implemented or not yet validated as production features

These must not be presented as if they already work:

1. Verified newly-listed coin discovery from official exchange listing timestamps.
2. Reliable market cap, FDV, circulating supply, token unlocks, holder concentration, contract audits, and on-chain wallet intelligence.
3. Comprehensive project research agent that verifies official sources, cross-checks news, classifies rumours, and assesses catalyst timing.
4. Full MEXC-vs-Bybit identity resolution, cross-exchange lead/lag analysis, and arbitrage analysis.
5. Full futures open-interest history, liquidation maps, order-book depth history, and large-trade detection.
6. Persistent first-seen tracking across restarts and robust listing event history.
7. Automatic forward outcome labelling (+10%, +25%, +50%, +100%, maximum adverse excursion) and strategy/backtest reports.
8. A trained, calibrated model connected to live ranking. The included trainer is offline only and requires enough clean labelled observations.
9. Verified 24/7 operation on free hosting. Free services can sleep, restart, rate-limit, or change terms.
10. Automated trading. No order placement is included by design.

## Recommended next technical milestones

1. Deploy separately from the existing scanner and verify live data/source status.
2. Move persistent storage to PostgreSQL where a suitable free allowance is available; implement migrations and backup/export.
3. Add robust persistent first-seen records and explicit listing events sourced from official exchange announcement feeds.
4. Store signal snapshots with stable candidate IDs and calculate forward outcomes at defined horizons without look-ahead leakage.
5. Add order-book, trade flow, funding, and open-interest features where supported and rate-limit-safe.
6. Add reliable official-source project/news feeds and explicit “coverage incomplete” states.
7. Build labelled data, evaluate baselines on chronological holdouts, and only then consider live model integration.
8. Validate each signal with realistic fees, spread, slippage, missed data, delisted assets, and out-of-sample periods before using real money.
