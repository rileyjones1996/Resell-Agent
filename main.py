"""
Entry point — runs the bot in paper mode or kicks off a backtest.

Usage:
    python main.py                                  # paper mode (live feed placeholder)
    python main.py --backtest data/sample_ES_1min.csv
    python main.py --backtest data/ES_20240115.csv --label ES_20240115
    python main.py --backtest data/ES.csv --no-export
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
        "Account: $%.2f  |  Max daily loss: $%.2f  |  Max drawdown: $%.2f  |  Stop: %.1f%%",
        CONFIG.risk.account_size,
        CONFIG.risk.max_daily_loss_dollars,
        CONFIG.risk.max_trailing_drawdown_dollars,
        CONFIG.strategy.stop_size_pct * 100,
    )
    logger.warning(
        "Live market data feed not yet connected — "
        "implement a real-time source in src/feeds/market_data.py"
    )


def run_backtest(csv_path: str, label: str, no_export: bool) -> None:
    from backtest.runner import run_backtest as _run

    path = Path(csv_path)
    if not path.exists():
        logger.error("CSV not found: %s", csv_path)
        sys.exit(1)

    logger.info("Starting backtest: %s", path)
    results = _run(path, run_label=label, export=not no_export)

    # Print human-readable summary to stdout
    print("\n" + "=" * 50)
    print("  BACKTEST RESULTS")
    print("=" * 50)
    fields = [
        ("Bars processed",  "bars_processed",  "{}"),
        ("Total trades",    "total_trades",    "{}"),
        ("Winners",         "winners",         "{}"),
        ("Losers",          "losers",          "{}"),
        ("Win rate",        "win_rate",        "{:.1%}"),
        ("Total P&L",       "total_pnl",       "${:.2f}"),
        ("Avg win",         "avg_win",         "${:.4f}" ),
        ("Avg loss",        "avg_loss",        "${:.4f}"),
        ("Profit factor",   "profit_factor",   "{:.4f}"),
        ("Max drawdown",    "max_drawdown",    "${:.2f}"),
        ("Expectancy",      "expectancy",      "${:.4f}/trade"),
        ("Final equity",    "final_equity",    "${:.2f}"),
        ("Signals fired",   "signals_fired",   "{}"),
        ("  Accepted",      "signals_accepted","{}"),
        ("  Rejected",      "signals_rejected","{}"),
        ("Risk halted",     "risk_halted",     "{}"),
        ("Halt reason",     "halt_reason",     "{}"),
    ]
    for label_str, key, fmt in fields:
        val = results.get(key)
        if val is None:
            display = "N/A"
        else:
            try:
                display = fmt.format(val)
            except (TypeError, ValueError):
                display = str(val)
        print(f"  {label_str:<18}: {display}")
    print("=" * 50)

    if not no_export:
        print(f"\n  Journals exported to: {CONFIG.export_dir}/")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prop-firm trading bot (paper only)")
    parser.add_argument(
        "--backtest",
        metavar="CSV",
        help="Path to OHLCV CSV file for backtesting",
    )
    parser.add_argument(
        "--label",
        default="",
        metavar="LABEL",
        help="Label appended to exported journal filenames",
    )
    parser.add_argument(
        "--no-export",
        action="store_true",
        help="Skip writing trade/signal journals to disk",
    )
    args = parser.parse_args()

    if not CONFIG.paper_mode and args.backtest is None:
        logger.error("Live mode is disabled — set PAPER_MODE=true in .env")
        sys.exit(1)

    if args.backtest:
        run_backtest(args.backtest, label=args.label, no_export=args.no_export)
    else:
        run_paper()


if __name__ == "__main__":
    main()
