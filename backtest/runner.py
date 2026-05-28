"""
Backtest runner — feeds CSV bars through strategy + risk + paper engine.
Results are logged and returned as a dict; no results are fabricated.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Any

from config.settings import CONFIG
from src.feeds.market_data import CSVMarketFeed
from src.signals.strategy import VWAPStrategy, Signal
from src.risk.risk_manager import RiskManager
from src.execution.paper_engine import PaperEngine
from src.utils.logger import setup_logger

logger = logging.getLogger(__name__)


def run_backtest(csv_path: Path) -> Dict[str, Any]:
    """
    Run a full backtest over the given CSV file.

    Returns a summary dict — does NOT overstate results.
    """
    feed = CSVMarketFeed(csv_path)
    strategy = VWAPStrategy(CONFIG.strategy)
    risk = RiskManager(CONFIG.risk)
    engine = PaperEngine()

    bars = feed.all_bars()
    if not bars:
        raise ValueError(f"No bars loaded from {csv_path}")

    logger.info("Backtest started — %d bars, file=%s", len(bars), csv_path.name)

    for i, bar in enumerate(bars):
        # 1. Update paper engine (fills pending orders, checks stops)
        realized_pnl = engine.on_bar(bar)

        # 2. Update risk state
        risk.update_equity(
            realized_pnl_delta=realized_pnl,
            unrealized_pnl=engine.unrealized_pnl(bar.close),
            trade_date=bar.timestamp.date(),
        )

        if not risk.can_trade():
            logger.info("Risk halt active — skipping signal generation (bar %d)", i)
            continue

        # 3. Generate signal
        analysis = strategy.on_bar(bar)

        if analysis.signal == Signal.FLAT:
            continue

        # 4. Validate position size against risk rules
        proposed_risk = CONFIG.risk.max_position_dollars
        if not risk.position_size_ok(proposed_risk):
            logger.warning("Position size rejected: %.2f > limit %.2f", proposed_risk, risk.max_allowed_risk())
            continue

        # 5. Submit to paper engine
        order = engine.on_signal(analysis.signal, bar)
        if order is not None:
            risk.record_trade()

    # Close any open position at the last bar's close
    if engine.position is not None and bars:
        last = bars[-1]
        engine.close_all(last.close, last.timestamp)

    summary = engine.summary()
    summary["risk_halted"] = risk.state.halted
    summary["halt_reason"] = risk.state.halt_reason
    summary["final_equity"] = round(risk.state.equity, 2)
    summary["bars_processed"] = len(bars)

    logger.info(
        "Backtest complete — trades=%d  pnl=%.2f  win_rate=%.1f%%  halted=%s",
        summary["total_trades"],
        summary["total_pnl"],
        summary["win_rate"] * 100,
        summary["risk_halted"],
    )
    return summary
