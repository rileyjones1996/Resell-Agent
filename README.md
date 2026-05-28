# Prop-Firm Trading Bot Foundation

Paper-mode trading bot designed around **Apex-style** prop-firm evaluation rules.
No live orders are ever placed — all execution is simulated.

---

## Project Structure

```
trading-system/
├── config/
│   └── settings.py          # Typed config loaded from .env
├── src/
│   ├── feeds/
│   │   └── market_data.py   # CSV bar feed (swap for live feed later)
│   ├── risk/
│   │   └── risk_manager.py  # Apex-style risk rules + halt logic
│   ├── signals/
│   │   └── strategy.py      # VWAP + RSI + trend filter strategy
│   ├── execution/
│   │   └── paper_engine.py  # Simulated paper order fills
│   └── utils/
│       └── logger.py        # Rotating file + console logging
├── backtest/
│   └── runner.py            # Full backtest loop over CSV
├── data/
│   └── sample_ES_1min.csv   # Sample 1-min ES futures data
├── logs/                    # Auto-created at runtime
├── tests/
│   ├── test_risk_manager.py
│   ├── test_strategy.py
│   └── test_paper_engine.py
├── main.py                  # Entry point
├── .env                     # Your local config (not committed)
├── .env.example             # Template — copy to .env
└── requirements.txt
```

---

## Setup

```bash
# 1. Create a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your account size and risk parameters
```

---

## Risk Rules (Apex-Style)

| Rule | Default | Env var |
|------|---------|---------|
| Max daily loss | 3% of account | `MAX_DAILY_LOSS_PCT` |
| Max trailing drawdown | 5% of account | `MAX_TRAILING_DRAWDOWN_PCT` |
| Max position size (risk) | 2% of account | `MAX_POSITION_SIZE_PCT` |
| Max trades per day | 10 | `MAX_TRADES_PER_DAY` |

Once any rule is breached, trading halts for the session. Peak equity is tracked from session start for drawdown calculation.

---

## Running Tests

```bash
# All tests
pytest

# With coverage report
pytest --cov=src --cov=config --cov=backtest --cov-report=term-missing

# Specific test file
pytest tests/test_risk_manager.py -v
```

---

## Running the Bot

### Paper Mode (live feed placeholder)

```bash
python main.py
```

This starts paper mode. A live market data feed is not yet wired in — implement a real-time source in `src/feeds/market_data.py` and call `CSVMarketFeed` → your live feed class.

### Backtest Mode

```bash
python main.py --backtest data/sample_ES_1min.csv
```

Feeds the CSV file through the full strategy + risk + paper engine loop and prints a summary.

To use your own data, drop a CSV with these columns into `data/`:
```
timestamp,open,high,low,close,volume
2024-01-15 09:30,4780.00,4782.50,4779.00,4781.75,1200
```

---

## Strategy Overview

**Indicators:**
- **VWAP** — resets each calendar day; price deviation from VWAP gates entries
- **RSI(14)** — standard momentum oscillator
- **Trend filter** — 20-bar SMA; only trades in the direction of the trend

**Entry logic:**
- LONG: `close > VWAP + threshold` AND `RSI < 30` AND trend is UP
- SHORT: `close < VWAP - threshold` AND `RSI > 70` AND trend is DOWN

**Placeholders (not yet implemented):**
- Key level detection — `strategy.key_level_near(price)` returns `None`
- Order-flow bias — `strategy.order_flow_bias()` returns `None`

---

## Configuration Reference

All settings can be overridden in `.env`:

```bash
ACCOUNT_SIZE=50000.0
PAPER_MODE=true
MAX_DAILY_LOSS_PCT=0.03
MAX_TRAILING_DRAWDOWN_PCT=0.05
MAX_POSITION_SIZE_PCT=0.02
MAX_TRADES_PER_DAY=10
RSI_PERIOD=14
RSI_OVERBOUGHT=70
RSI_OVERSOLD=30
VWAP_DEVIATION_THRESHOLD=0.001
DATA_DIR=data
LOG_DIR=logs
LOG_LEVEL=INFO
```

---

## Logs

Logs are written to `logs/main.log` (rotating, 5 MB max, 3 backups) and to stdout.

---

## What Is NOT Implemented

- Live broker connectivity (intentionally absent)
- Real order-flow data
- Key level detection
- Walk-forward optimization
- Position sizing beyond flat-dollar risk cap
