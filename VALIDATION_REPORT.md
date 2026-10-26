# Local validation report

Checks run while preparing this ZIP:

- Python compilation (`python -m py_compile app.py`): passed.
- Unit/API tests (`python -m unittest discover -s tests -v`): 6 passed.
- Dashboard HTML response test: passed.
- Health, market API, and config API tests: passed.
- Inline dashboard JavaScript syntax check with Node.js (`node --check`): passed.
- ZIP integrity: checked before delivery.

## What this does not mean

These are local deterministic checks. This environment did not verify live Bybit/MEXC API availability, Render deployment, RSS feed reliability, Telegram delivery, or PostgreSQL provisioning. The checks do not prove the scanner predicts pumps, 10x/100x outcomes, or profitable entries. Verify `/api/status`, `/api/config`, source health, and logs after deployment before relying on the data.
