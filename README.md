## Torn Trainer (read‑only, no Docker)

A safe, read‑only Torn City helper that recommends when to train, which crimes to prefer, and when to buy/sell watched market items. It never performs in‑game actions. All API calls and recommendations are audit‑logged to SQLite and rotating log files.

Built for Python 3.11+, async via `httpx` with a token‑bucket rate limiter. Minimal, privacy‑respecting, and easy to run on Windows/macOS/Linux.

### What you get
- Read‑only trainer and helper: recommendations only
- Async Torn API client with retries, backoff, jitter, and rate limiting (60 req/min default; up to 100)
- CLI: `start`, `run-once`, `dry-run`, `status`
- Audit: SQLite DB + rotating logs
- Market watch alerts

### Quick start
1) Install Python 3.11+.
2) Create a virtual environment and install dependencies.
   - Windows (PowerShell):
     ```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
     ```
   - macOS/Linux:
     ```bash
python3 -m venv .venv
. ./.venv/bin/activate
pip install -r requirements.txt
     ```
3) Add your Torn credentials (do not share these):
   - Create `.env` in the project folder with:
     ```
API_KEY=YOUR_TORN_API_KEY
USER_ID=YOUR_TORN_USER_ID
MAX_REQUESTS_PER_MIN=60
SAFE_SPACING_SECONDS=1.0
DB_PATH=torn.db
LOG_LEVEL=INFO
LOG_DIR=logs
     ```
   - Alternatively, you can set environment variables in your shell session.

4) Run a safe dry‑run first:
   - Windows:
     ```powershell
.\.venv\Scripts\python.exe -m src.run_trainer run-once --dry-run --log-level INFO
     ```
   - macOS/Linux:
     ```bash
python -m src.run_trainer run-once --dry-run --log-level INFO
     ```

5) Optional: watch market items (repeat flag allowed):
```powershell
.\.venv\Scripts\python.exe -m src.run_trainer run-once --dry-run --market-watch 108:35000:50000 --log-level INFO
```

6) Continuous run:
```powershell
.\.venv\Scripts\python.exe -m src.run_trainer start --log-level INFO
```

### How it decides
- Gym: recommends training when `energy >= threshold` (default 90). Logs a plan and prints a safe, read‑only snippet.
- Crimes: when `nerve >= threshold` (default 30) and no crime cooldown, prefers crimes with the highest expected cash‑per‑nerve from the `torn` crimes data.
- Market: monitors configured item IDs; alerts when price crosses buy/sell thresholds.

It never performs write actions. It prints recommendations and logs planned actions to the DB.

### CLI overview
- `run-once`: one decision loop, prints recommendations
- `start`: continuous scheduler loop
- `dry-run`: alias of `run-once` with `--dry-run`
- `status`: prints last snapshot stored in SQLite

Common options:
- `--max-requests-per-min` (default 60, max 100)
- `--energy-threshold` (default 90)
- `--nerve-threshold` (default 30)
- `--log-level` (DEBUG, INFO, WARNING, ERROR)
- `--market-watch ITEM_ID:BUY:SELL` (repeatable)
- `--simulate-money` (use synthetic user money for testing)

Examples:
```powershell
.\.venv\Scripts\python.exe -m src.run_trainer run-once --dry-run --market-watch 108:35000:50000 --market-watch 17:8000:12000
.\.venv\Scripts\python.exe -m src.run_trainer start --max-requests-per-min 80 --energy-threshold 95 --nerve-threshold 35
```

### Safety, etiquette, and privacy
- Read‑only: no in‑game write actions are sent.
- Conservative defaults: 60 req/min, ≥1s spacing, jitter, retries on 429/5xx.
- Repeated auth errors mark your key as disabled in the DB to stop further calls.
- Your API key and user ID live only in your local `.env` or env vars; logs redact the key.

### Logs and database
- Logs: `logs/trainer.log` with rotating file handler + console output
- SQLite DB: `torn.db` (created automatically)
  - `actions(id,timestamp,action_type,payload,result_json)`
  - `snapshots(ts,json)`
  - `keys(id,key,disabled_at)`
  - `market_watch(item_id,buy_threshold,sell_threshold,last_seen_price)`

### Tests
```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

### Troubleshooting
- Empty recommendations: your energy/nerve may be below thresholds, or a crime cooldown is active. Lower thresholds using CLI flags and try again.
- Key disabled: fix/replace your key, then delete the `keys` row or use a new `USER_ID` key id.
- Network/API errors: see `logs/trainer.log` and the `actions` table for statuses and payload snippets.
- Rate limits: keep spacing ≥ 1s; do not exceed 100 req/min.

### Important
You are responsible for ensuring your usage complies with Torn rules. This tool is read‑only and prints recommendations only.

