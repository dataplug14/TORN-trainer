# Torn Trainer

**Lead Developer:** @dataplug14  
**License:** MIT  
**Python:** 3.11+

A smart, read-only assistant for Torn City that helps you optimize your gameplay without breaking any rules. Think of it as your personal advisor that watches your stats and tells you the best times to train, which crimes are most profitable, and when market prices hit your targets.

**Important:** This tool is completely read-only. It never performs any in-game actions - it just gives you recommendations that you can choose to follow or ignore.

## Features

- **Smart Training Recommendations** - Tells you when your energy is high enough to make training worthwhile
- **Crime Optimization** - Calculates which crimes give you the best cash-per-nerve ratio
- **Market Monitoring** - Watches items you care about and alerts when prices hit your buy/sell targets
- **Bulletproof API Client** - Handles rate limits, retries, and errors gracefully so you don't get banned
- **Complete Audit Trail** - Everything is logged to SQLite and files so you can see exactly what happened
- **Cross-Platform** - Works on Windows, macOS, and Linux

## Getting Started

### 1. Install Python 3.11+
Make sure you have Python 3.11 or newer installed.

### 2. Set up the environment

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

**macOS/Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure your credentials

Create a `.env` file in the project root with your Torn API details:

```env
API_KEY=your_torn_api_key_here
USER_ID=your_torn_user_id
MAX_REQUESTS_PER_MIN=60
SAFE_SPACING_SECONDS=1.0
DB_PATH=torn.db
LOG_LEVEL=INFO
LOG_DIR=logs
```

**⚠️ Keep your API key private!** Don't share it or commit it to version control.

### 4. Test it out

Always run a dry-run first to make sure everything works:

**Windows:**
```powershell
.\.venv\Scripts\python.exe -m src.run_trainer run-once --dry-run
```

**macOS/Linux:**
```bash
python -m src.run_trainer run-once --dry-run
```

### 5. Start using it

For continuous monitoring:
```powershell
.\.venv\Scripts\python.exe -m src.run_trainer start
```

To watch specific market items:
```powershell
.\.venv\Scripts\python.exe -m src.run_trainer start --market-watch 108:35000:50000
```

## How It Works

The logic is pretty straightforward:

**Training:** When your energy hits the threshold (default: 90), it recommends which gym to hit based on your current stats and what you're trying to improve.

**Crimes:** When you have enough nerve (default: 30) and no crime cooldown, it calculates which crimes give you the best return on investment and suggests those.

**Market:** Continuously monitors items you specify and alerts you when prices cross your buy/sell thresholds.

Everything is logged to the database so you can track patterns and see what recommendations were made when.

## Commands

- `run-once` - Check your stats once and give recommendations
- `start` - Run continuously, checking periodically
- `dry-run` - Same as `run-once --dry-run` (safe testing)
- `status` - Show your last recorded stats

### Useful Options

- `--energy-threshold 90` - When to recommend training (default: 90)
- `--nerve-threshold 30` - When to recommend crimes (default: 30)
- `--max-requests-per-min 60` - API rate limit (max: 100)
- `--market-watch ITEM_ID:BUY:SELL` - Monitor market prices
- `--log-level INFO` - How verbose to be (DEBUG, INFO, WARNING, ERROR)

### Examples

```powershell
# Test with market monitoring
.\.venv\Scripts\python.exe -m src.run_trainer dry-run --market-watch 108:35000:50000

# Run continuously with custom thresholds
.\.venv\Scripts\python.exe -m src.run_trainer start --energy-threshold 95 --nerve-threshold 35

# Monitor multiple market items
.\.venv\Scripts\python.exe -m src.run_trainer start --market-watch 108:35000:50000 --market-watch 17:8000:12000
```

## Safety & Privacy

This tool was built with safety as the top priority:

- **100% Read-Only** - It literally cannot perform any in-game actions. The code doesn't even have the capability.
- **Respectful Rate Limiting** - Conservative 60 requests/minute default with smart spacing and jitter
- **Auto-Disable on Auth Errors** - If your key gets revoked, it stops making requests automatically
- **Local Data Only** - Your credentials never leave your machine. API keys are redacted from logs.
- **Torn-Friendly** - Built to respect Torn's API limits and terms of service

## Data Storage

Everything is stored locally on your machine:

- **Logs:** `logs/trainer.log` (rotates automatically to prevent huge files)
- **Database:** `torn.db` SQLite file with tables for:
  - Actions taken and their results
  - Snapshots of your stats over time
  - API key status
  - Market watch configurations and price history

## Development

Run the tests:
```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## Troubleshooting

**"No recommendations"** - Your energy/nerve might be below the thresholds, or you might have a crime cooldown active. Try lowering the thresholds with `--energy-threshold` or `--nerve-threshold`.

**"Key disabled"** - Your API key got revoked or changed. Update your `.env` file and delete the old key from the database, or just delete the whole `torn.db` file to start fresh.

**Network errors** - Check `logs/trainer.log` for details. The tool handles most API errors gracefully, but persistent issues usually mean API problems on Torn's end.

**Rate limit issues** - Don't go above 100 requests/minute, and keep spacing at least 1 second. The defaults are conservative for a reason.

## Disclaimer

This tool is completely read-only and only provides recommendations. You're responsible for ensuring your usage complies with Torn City's rules and terms of service. When in doubt, ask the Torn staff.

---

**Questions or issues?** Open an issue on GitHub or reach out to me.

**Like this project?** Give it a star ⭐ and maybe buy me a coffee!

