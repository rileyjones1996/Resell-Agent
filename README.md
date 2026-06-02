# Prop-Firm Trading Bot Foundation

Paper-mode trading bot designed around **Apex-style** prop-firm evaluation rules.  
No live orders are ever placed — all execution is simulated.

---

## Project Structure

```
trading-system/
├── .env                        ← your local config (gitignored)
├── .env.example                ← template — copy to .env and edit
├── config/
│   └── settings.py             ← typed config loaded from .env
├── src/
│   ├── feeds/
│   │   └── market_data.py      ← CSV bar feed (Bar dataclass + CSVMarketFeed)
│   ├── risk/
│   │   └── risk_manager.py     ← Apex-style 5-rule risk manager + halt logic
│   ├── signals/
│   │   └── strategy.py         ← VWAP + RSI + SMA trend filter strategy
│   ├── execution/
│   │   └── paper_engine.py     ← Simulated paper fills, stop-loss, no live orders
│   └── utils/
│       └── logger.py           ← Rotating file + stdout logging
├── backtest/
│   ├── runner.py               ← Full bar-by-bar backtest loop
│   ├── metrics.py              ← Rich performance metrics (P&L, drawdown, etc.)
│   └── journal.py              ← Trade + signal journal CSV/JSON export
├── data/
│   └── sample_ES_1min.csv      ← Sample 30-bar ES futures data (smoke test only)
├── exports/                    ← Auto-created — journal files written here
├── logs/                       ← Auto-created — rotating log files
├── tests/
│   ├── test_risk_manager.py    ← 17 risk rule tests
│   ├── test_strategy.py        ← 12 indicator tests
│   ├── test_paper_engine.py    ← 11 execution tests
│   ├── test_metrics.py         ← 14 metrics tests
│   ├── test_journal.py         ← 12 export tests
│   └── test_backtest_integration.py ← 6 end-to-end pipeline tests
├── main.py                     ← Entry point
├── requirements.txt
└── README.md
```

---

## Setup

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env — set your account size, risk limits, strategy params
```

---

## Environment Variables

All settings live in `.env` (copy from `.env.example`):

| Variable | Default | Description |
|---|---|---|
| `ACCOUNT_SIZE` | `50000.0` | Paper account equity in dollars |
| `PAPER_MODE` | `true` | Must be true — live mode not implemented |
| `MAX_DAILY_LOSS_PCT` | `0.03` | Max daily loss as % of account (3% = $1,500 on $50k) |
| `MAX_TRAILING_DRAWDOWN_PCT` | `0.05` | Max trailing drawdown from equity peak (5%) |
| `MAX_POSITION_SIZE_PCT` | `0.02` | Max risk per trade as % of account (2%) |
| `MAX_TRADES_PER_DAY` | `10` | Hard cap on entries per calendar day |
| `RSI_PERIOD` | `14` | RSI lookback period |
| `RSI_OVERBOUGHT` | `70` | RSI level for short signal |
| `RSI_OVERSOLD` | `30` | RSI level for long signal |
| `VWAP_ENABLED` | `true` | Use VWAP as entry gate |
| `VWAP_DEVIATION_THRESHOLD` | `0.001` | Min % deviation from VWAP to trigger entry |
| `SMA_PERIOD` | `20` | SMA period for trend filter |
| `STOP_SIZE_PCT` | `0.005` | Stop distance from entry as % (0.5%) |
| `DATA_DIR` | `data` | Folder to look for CSV files |
| `LOG_DIR` | `logs` | Folder for rotating log files |
| `EXPORT_DIR` | `exports` | Folder for trade/signal journal exports |
| `LOG_LEVEL` | `INFO` | Python logging level |

---

## Risk Rules (Apex-Style)

Once any rule is breached, trading halts for the session.  
Peak equity is tracked from session start for the trailing drawdown calculation.

| Rule | What triggers it |
|---|---|
| Max daily loss | Realized + unrealized PnL drops below `−MAX_DAILY_LOSS_PCT × account` |
| Max trailing drawdown | Equity falls `MAX_TRAILING_DRAWDOWN_PCT × account` from its peak |
| Max position size | A proposed trade's dollar risk exceeds `MAX_POSITION_SIZE_PCT × account` |
| Max trades per day | Entry count reaches `MAX_TRADES_PER_DAY` for the calendar day |
| Post-halt lockout | Once halted by any rule, no new entries are allowed |

---

## Strategy

**Indicators** (all computed from closed bars — no lookahead bias):
- **VWAP** — resets each calendar day; price deviation from VWAP gates entries
- **RSI(N)** — configurable period via `RSI_PERIOD`
- **SMA(N)** — N-bar simple moving average used as trend filter; N set by `SMA_PERIOD`

**Entry logic:**
- **LONG**: `close > VWAP + threshold` **AND** `RSI < RSI_OVERSOLD` **AND** trend = UP
- **SHORT**: `close < VWAP - threshold` **AND** `RSI > RSI_OVERBOUGHT` **AND** trend = DOWN

**Placeholders (not yet implemented):**
- `strategy.key_level_near(price)` — returns `None` until key-level detection is wired in
- `strategy.order_flow_bias()` — returns `None` until order-flow data is available

---

## Running Tests

```bash
# Run all 73 tests
pytest

# With coverage report
pytest --cov=src --cov=config --cov=backtest --cov-report=term-missing

# Specific module
pytest tests/test_risk_manager.py -v
pytest tests/test_metrics.py -v
```

---

## Running the Bot

### Paper mode (live feed placeholder)

```bash
python main.py
```

Starts paper mode. Logs account config and warns that a live data source is not wired in.  
To add real-time data: implement a feed class in `src/feeds/market_data.py` with the same `bars()` / `all_bars()` interface as `CSVMarketFeed`.

### Backtest over a CSV file

```bash
# Basic — uses data/sample_ES_1min.csv
python main.py --backtest data/sample_ES_1min.csv

# With a label appended to journal filenames
python main.py --backtest data/ES_20240115.csv --label ES_20240115

# Skip writing export files
python main.py --backtest data/ES.csv --no-export
```

**CSV format** (columns are case-insensitive):
```
timestamp,open,high,low,close,volume
2024-01-15 09:30,4780.00,4782.50,4779.00,4781.75,1200
```

Drop any ES / NQ / MES / MNQ 1-min CSV into `data/` and pass its path via `--backtest`.

---

## Backtest Output

Each run prints a results table and writes two files to `exports/`:

```
==================================================
  BACKTEST RESULTS
==================================================
  Bars processed    : 30
  Total trades      : 0
  Winners           : 0
  Losers            : 0
  Win rate          : 0.0%
  Total P&L         : $0.00
  Avg win           : N/A
  Avg loss          : N/A
  Profit factor     : N/A
  Max drawdown      : $0.00
  Expectancy        : $0.0000/trade
  Final equity      : $50000.00
  Signals fired     : 0
    Accepted        : 0
    Rejected        : 0
  Risk halted       : False
  Halt reason       :
==================================================
```

**Export files** (in `exports/`):

| File | Contents |
|---|---|
| `trades_<label>.csv` | One row per closed trade: entry/exit price, PnL, exit reason |
| `trades_<label>.json` | Same data in JSON format |
| `signals_<label>.csv` | Every non-FLAT signal: VWAP, RSI, SMA, trend, accepted/rejected + reason |
| `signals_<label>.json` | Same data in JSON format |

---

## Logs

Written to `logs/main.log` — rotating, 5 MB max, 3 backups.  
All fill, halt, signal-accepted, and signal-rejected events are logged with timestamps.

---

## What Is NOT Implemented

- Live broker connectivity (intentionally absent)
- Real-time order-flow data
- Key level detection
- Walk-forward optimization / parameter search
- Position sizing beyond flat-dollar risk cap
- Replay mode (planned next)
