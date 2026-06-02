"""
Backtest runner — feeds CSV bars through strategy + risk + paper engine.
Results are logged and returned as a dict; no results are fabricated.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.settings import CONFIG
from src.feeds.market_data import CSVMarketFeed
from src.signals.strategy import VWAPStrategy, Signal
from src.risk.risk_manager import RiskManager
from src.execution.paper_engine import PaperEngine
from backtest.metrics import compute_metrics
from backtest.journal import SignalRecord, export_trades, export_signals

logger = logging.getLogger(__name__)


def run_backtest(
    csv_path: Path,
    run_label: str = "",
    export: bool = True,
) -> Dict[str, Any]:
    """
    Run a full backtest over the given CSV file.

    Args:
        csv_path:   path to the OHLCV CSV
        run_label:  appended to export filenames (e.g. "ES_20240115")
        export:     write trade/signal journals to CONFIG.export_dir if True

    Returns a rich summary dict — does NOT fabricate results.
    """
    feed = CSVMarketFeed(csv_path)
    strategy = VWAPStrategy(CONFIG.strategy)
    risk = RiskManager(CONFIG.risk)
    engine = PaperEngine(stop_size_pct=CONFIG.strategy.stop_size_pct)

    bars = feed.all_bars()
    if not bars:
        raise ValueError(f"No bars loaded from {csv_path}")

    logger.info(
        "Backtest started — %d bars | file=%s | account=$%.2f | "
        "max_daily_loss=$%.2f | max_drawdown=$%.2f | max_trades=%d",
        len(bars),
        csv_path.name,
        CONFIG.risk.account_size,
        CONFIG.risk.max_daily_loss_dollars,
        CONFIG.risk.max_trailing_drawdown_dollars,
        CONFIG.risk.max_trades_per_day,
    )

    signal_journal: List[SignalRecord] = []

    for i, bar in enumerate(bars):
        # 1. Fill pending orders + check stops
        realized_pnl = engine.on_bar(bar)

        # 2. Update risk state
        risk.update_equity(
            realized_pnl_delta=realized_pnl,
            unrealized_pnl=engine.unrealized_pnl(bar.close),
            trade_date=bar.timestamp.date(),
        )

        if not risk.can_trade():
            if i == 0 or bars[i - 1].timestamp.date() == bar.timestamp.date():
                logger.info(
                    "HALT active | bar=%d | %s | reason: %s",
                    i,
                    bar.timestamp,
                    risk.state.halt_reason,
                )
            continue

        # 3. Generate signal — no future data used
        analysis = strategy.on_bar(bar)

        if analysis.signal == Signal.FLAT:
            continue

        # 4. Determine if the signal is accepted or rejected
        rejection_reason = _rejection_reason(engine, risk)
        accepted = rejection_reason == ""

        signal_journal.append(
            SignalRecord(
                timestamp=bar.timestamp,
                bar_close=bar.close,
                signal=analysis.signal.value,
                vwap=analysis.vwap,
                rsi=analysis.rsi,
                sma=analysis.sma,
                trend=analysis.trend,
                accepted=accepted,
                rejection_reason=rejection_reason,
            )
        )

        if not accepted:
            logger.info(
                "Signal REJECTED | %s | %s | close=%.4f | reason=%s",
                bar.timestamp,
                analysis.signal.value,
                bar.close,
                rejection_reason,
            )
            continue

        # 5. Submit to paper engine
        order = engine.on_signal(analysis.signal, bar)
        if order is not None:
            risk.record_trade()
            logger.info(
                "Signal ACCEPTED | %s | %s | close=%.4f | vwap=%.4f | rsi=%.1f | trend=%s",
                bar.timestamp,
                analysis.signal.value,
                bar.close,
                analysis.vwap,
                analysis.rsi or 0,
                analysis.trend,
            )

    # Close any open position at the last bar's close
    if engine.position is not None and bars:
        last = bars[-1]
        engine.close_all(last.close, last.timestamp)

    # Compute rich metrics
    metrics = compute_metrics(
        engine.trades,
        starting_equity=CONFIG.risk.account_size,
        halt_reason=risk.state.halt_reason,
    )

    summary: Dict[str, Any] = {
        **metrics,
        "risk_halted": risk.state.halted,
        "final_equity": round(risk.state.equity, 2),
        "bars_processed": len(bars),
        "signals_fired": len(signal_journal),
        "signals_accepted": sum(1 for s in signal_journal if s.accepted),
        "signals_rejected": sum(1 for s in signal_journal if not s.accepted),
    }

    _log_summary(summary)

    if export and signal_journal or engine.trades:
        export_trades(engine.trades, CONFIG.export_dir, run_label)
        export_signals(signal_journal, CONFIG.export_dir, run_label)

    return summary


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _rejection_reason(engine: PaperEngine, risk: RiskManager) -> str:
    """Return the reason a non-FLAT signal should be rejected, or '' if it's ok."""
    if not risk.can_trade():
        return f"risk_halt:{risk.state.halt_reason}"
    if engine._pending_order is not None:
        return "pending_order_exists"
    proposed = CONFIG.risk.max_position_dollars
    if not risk.position_size_ok(proposed):
        return f"position_too_large:{proposed:.2f}>{risk.max_allowed_risk():.2f}"
    return ""


def _log_summary(s: Dict[str, Any]) -> None:
    logger.info("=" * 60)
    logger.info("BACKTEST COMPLETE")
    logger.info("  Bars processed   : %d", s["bars_processed"])
    logger.info("  Total trades     : %d", s["total_trades"])
    logger.info("  Winners / Losers : %d / %d", s["winners"], s["losers"])
    logger.info("  Win rate         : %.1f%%", s["win_rate"] * 100)
    logger.info("  Total P&L        : $%.2f", s["total_pnl"])
    logger.info("  Avg win          : %s", f"${s['avg_win']:.4f}" if s["avg_win"] is not None else "N/A")
    logger.info("  Avg loss         : %s", f"${s['avg_loss']:.4f}" if s["avg_loss"] is not None else "N/A")
    logger.info("  Profit factor    : %s", f"{s['profit_factor']:.4f}" if s["profit_factor"] is not None else "N/A")
    logger.info("  Max drawdown     : $%.2f", s["max_drawdown"])
    logger.info("  Expectancy       : $%.4f/trade", s["expectancy"])
    logger.info("  Final equity     : $%.2f", s["final_equity"])
    logger.info("  Signals fired    : %d (%d accepted, %d rejected)", s["signals_fired"], s["signals_accepted"], s["signals_rejected"])
    logger.info("  Risk halted      : %s", s["risk_halted"])
    if s["halt_reason"]:
        logger.info("  Halt reason      : %s", s["halt_reason"])
    logger.info("=" * 60)
