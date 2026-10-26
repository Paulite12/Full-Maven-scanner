# Full Maven Scanner

Full Maven Scanner is a **read-only, mobile-friendly cryptocurrency market-intelligence prototype**. It uses public market endpoints, transparent heuristics, optional RSS/Atom feeds, optional Telegram alerts, and a local SQLite or configured PostgreSQL database. It does not place trades and does not require exchange API keys for public market data.

## Dashboard pages

- **Overview:** market snapshot, search, venue filters, sorting, and current signals.
- **Early Gems:** rule-qualified early-activity/watch candidates with reasons and risk flags.
- **Momentum:** short-term price/volume activity.
- **Risk Watch:** heuristic risk flags.
- **Newly Observed:** symbols first noticed by this running process. This is not verified exchange listing-date detection; first-seen memory can reset after a restart.
- **News Intelligence:** configured RSS/Atom feed items and feed coverage status.
- **History & Performance:** saved market observations. This is not a win-rate report and does not measure forward outcomes yet.
- **System Status:** runtime settings, market counts, source status, and latest warnings.
- **Market details:** tap a market row to view current metrics, reasons, and risk flags.

## Important limitations

- This is a research tool, not financial advice or a proven pump predictor. Scores are rules-based and are not probabilities or buy recommendations.
- Bybit discovery is limited to the top USDT pairs by 24-hour turnover per configured market category (`MAX_SYMBOLS_PER_MARKET`, default 100); it does not scan every market. Each candidate's 5-minute candles are requested separately, so rate limits and source failures can leave indicators missing.
- MEXC is currently a secondary spot watchlist based on turnover. It is not yet a complete cross-exchange arbitrage or contract-identity system. Matching symbols do not prove that assets are the same token or that the asset is listed on Bybit.
- The current code does not reliably establish market capitalisation, circulating supply, FDV, contract risk, holder concentration, on-chain activity, unlock schedules, or official listing dates. Do not infer these from volume.
- RSS/Atom feeds are optional and incomplete. If a feed is not configured or fails, the dashboard must not be interpreted as showing no negative news. This is not a comprehensive project due-diligence agent.
- The included machine-learning script is an **optional baseline trainer**, not a trained model. It needs at least 500 labelled observations containing future returns measured strictly after detection time. More data and out-of-sample testing are strongly preferable.
- History currently stores repeated market observations and feed items; it does not automatically calculate whether each signal later reached +10%, +25%, +50%, +100%, or its maximum drawdown. Do not interpret observation history as model performance.
- Free hosting can sleep, restart, limit background tasks, or change quotas. SQLite on ephemeral hosting may be lost. Set `DATABASE_URL` to a persistent PostgreSQL service if available and keep backups. Availability and free-plan terms can change.
- No automated trading or exchange order placement is implemented.

## Run locally

Python 3.11+ recommended.

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Open `http://127.0.0.1:8000`. Health endpoint: `/health`. JSON endpoints:

- `/api/status`
- `/api/market?limit=1000`
- `/api/candidates?min_score=10`
- `/api/news`
- `/api/history?limit=100`
- `/api/config`

## Deploy as a separate Render service

1. Upload all files in this project to a **new** GitHub repository. Do not overwrite your existing working scanner.
2. In Render, create a new Web Service from the new repository.
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn app:app --host 0.0.0.0 --port $PORT`
5. Configure environment variables from `.env.example` in Render's Environment page. Never commit secrets.
6. After deployment, check `/health`, `/api/status`, `/api/market`, `/api/news`, `/api/history`, and `/api/config`.
7. Check source status and logs. A healthy web process does not prove that all external data sources are working.

`render.yaml` is a starting configuration. Confirm the current Render dashboard settings and current free-plan limits before deploying.

## Environment variables

- `POLL_SECONDS` — scan interval, minimum 30 seconds (default 60).
- `MAX_SYMBOLS_PER_MARKET` — maximum top-turnover pairs per Bybit category and MEXC list (default 100, max 500).
- `RELATIVE_VOLUME_THRESHOLD` — relative 5-minute turnover threshold (default 2.5).
- `PRICE_CHANGE_THRESHOLD` — absolute 5-minute price-change threshold in percent (default 1.0).
- `DATABASE_URL` — optional PostgreSQL URL.
- `SCANNER_DB_PATH` — SQLite fallback path (default `/tmp/full_maven_scanner.db`).
- `NEWS_FEED_URLS` — comma-separated RSS/Atom URLs.
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` — optional Telegram alerts. Keep both secret.
- `BYBIT_BASE_URL`, `MEXC_BASE_URL` — optional endpoint overrides for tests.
- `LOG_LEVEL` — logging level.

## Telegram alerts

Create a bot using Telegram's official BotFather, start a chat with it, and configure the bot token and chat ID in the hosting environment only. Never paste tokens into public files or commit them to GitHub. Alerts are best-effort and rate-limited per venue/symbol in a running process; restarting can reset in-memory cooldowns.

## Optional baseline model training

Install the optional dependencies:

```bash
pip install -r ml-requirements.txt
```

Prepare a CSV with `observed_at`, `relative_volume`, `change_5m`, `change_24h`, `turnover_24h`, and `future_return_pct`. The future return must be measured after the observation timestamp, using a clearly defined horizon and realistic trading costs where appropriate. Avoid look-ahead leakage and survivorship bias.

```bash
python scripts/train_baseline.py labelled_observations.csv --target-pct 10 --out artifacts/baseline_model.joblib
```

The script requires at least 500 labelled rows and chronological train/test separation. A model artifact is not automatically loaded into the live scanner. Evaluation does not prove profitability; check precision/recall, calibration, slippage, fees, market regimes, and performance on later unseen data.

## Tests

```bash
pip install -r requirements.txt
python -m unittest discover -s tests -v
```

The tests validate deterministic local analysis and API behavior. They do not establish live exchange availability or predictive accuracy. The inline dashboard JavaScript can also be syntax-checked with Node.js if available.
