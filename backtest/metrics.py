"""
Backtest performance metrics — computed from a list of closed Trade objects.

Metrics returned:
  total_trades      — number of closed trades
  total_pnl         — sum of all P&L
  winners / losers  — count of profitable / losing trades
  win_rate          — winners / total_trades (0–1)
  avg_win           — mean P&L of winning trades
  avg_loss          — mean P&L of losing trades (negative number)
  profit_factor     — gross_wins / abs(gross_losses); None if no losses
  max_drawdown      — largest peak-to-trough equity drop from starting equity
  expectancy        — (win_rate * avg_win) + (loss_rate * avg_loss)
  halt_reason       — carried through from RiskManager

No results are fabricated.  All metrics are None / 0 when the trade list is empty.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.execution.paper_engine import Trade


def compute_metrics(
    trades: List[Trade],
    starting_equity: float,
    halt_reason: str = "",
) -> Dict[str, Any]:
    if not trades:
        return {
            "total_trades": 0,
            "total_pnl": 0.0,
            "winners": 0,
            "losers": 0,
            "win_rate": 0.0,
            "avg_win": None,
            "avg_loss": None,
            "profit_factor": None,
            "max_drawdown": 0.0,
            "expectancy": 0.0,
            "halt_reason": halt_reason,
        }

    winners = [t for t in trades if t.pnl > 0]
    losers = [t for t in trades if t.pnl <= 0]
    total = len(trades)

    win_rate = len(winners) / total
    loss_rate = 1.0 - win_rate

    avg_win: Optional[float] = (
        round(sum(t.pnl for t in winners) / len(winners), 4) if winners else None
    )
    avg_loss: Optional[float] = (
        round(sum(t.pnl for t in losers) / len(losers), 4) if losers else None
    )

    gross_wins = sum(t.pnl for t in winners)
    gross_losses = abs(sum(t.pnl for t in losers))
    profit_factor: Optional[float] = (
        round(gross_wins / gross_losses, 4) if gross_losses > 0 else None
    )

    # Expectancy: expected $ per trade
    expectancy = 0.0
    if avg_win is not None and avg_loss is not None:
        expectancy = round((win_rate * avg_win) + (loss_rate * avg_loss), 4)

    # Max drawdown: largest peak-to-trough in the running equity curve
    equity = starting_equity
    peak = equity
    max_dd = 0.0
    for t in trades:
        equity += t.pnl
        if equity > peak:
            peak = equity
        dd = peak - equity
        if dd > max_dd:
            max_dd = dd

    return {
        "total_trades": total,
        "total_pnl": round(sum(t.pnl for t in trades), 2),
        "winners": len(winners),
        "losers": len(losers),
        "win_rate": round(win_rate, 4),
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "profit_factor": profit_factor,
        "max_drawdown": round(max_dd, 2),
        "expectancy": expectancy,
        "halt_reason": halt_reason,
    }
