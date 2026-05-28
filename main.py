"""
Entry point — runs the bot in paper mode or kicks off a backtest.

Usage:
    python main.py                         # paper mode (waits for live feed)
    python main.py --backtest data/sample_ES_1min.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from config.settings import CONFIG
from src.utils.logger import setup_logger

logger = setup_logger("main", CONFIG.log_dir, CONFIG.log_level)


def run_paper() -> None:
    logger.info("Starting in PAPER mode")
    logger.info(
        "Account: $%.2f  |  Max daily loss: $%.2f  |  Max drawdown: $%.2f",
        CONFIG.risk.account_size,
        CONFIG.risk.max_daily_loss_dollars,
        CONFIG.risk.max_trailing_drawdown_dollars,
    )
    logger.warning(
        "Live market data feed not yet connected — "
        "implement a real-time data source in src/feeds/market_data.py"
    )


def run_backtest(csv_path: str) -> None:
    from backtest.runner import run_backtest as _run

    path = Path(csv_path)
    if not path.exists():
        logger.error("CSV not found: %s", csv_path)
        sys.exit(1)

    logger.info("Starting backtest: %s", path)
    results = _run(path)

    print("\n--- Backtest Results ---")
    for k, v in results.items():
        print(f"  {k}: {v}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prop-firm trading bot (paper only)")
    parser.add_argument(
        "--backtest",
        metavar="CSV",
        help="Path to OHLCV CSV file for backtesting",
    )
    args = parser.parse_args()

    if not CONFIG.paper_mode and args.backtest is None:
        logger.error("Live mode is disabled — set PAPER_MODE=true in .env")
        sys.exit(1)

    if args.backtest:
        run_backtest(args.backtest)
    else:
        run_paper()


if __name__ == "__main__":
    main()
