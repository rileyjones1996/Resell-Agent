"""
Paper execution engine — simulates order fills with no live connectivity.

Assumptions:
  - Market orders fill at the next bar's open price (realistic slippage model).
  - One position at a time (flat before entering opposite direction).
  - Stop-loss enforced on every bar's low/high.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from src.feeds.market_data import Bar
from src.signals.strategy import Signal

logger = logging.getLogger(__name__)


@dataclass
class Order:
    order_id: int
    side: str           # "BUY" or "SELL"
    quantity: float
    submitted_at: datetime
    fill_price: Optional[float] = None
    filled_at: Optional[datetime] = None

    @property
    def is_filled(self) -> bool:
        return self.fill_price is not None


@dataclass
class Position:
    side: str           # "LONG" or "SHORT"
    entry_price: float
    quantity: float
    entry_time: datetime
    stop_loss: Optional[float] = None

    def unrealized_pnl(self, current_price: float) -> float:
        if self.side == "LONG":
            return (current_price - self.entry_price) * self.quantity
        return (self.entry_price - current_price) * self.quantity

    def is_stopped(self, bar: Bar) -> bool:
        if self.stop_loss is None:
            return False
        if self.side == "LONG" and bar.low <= self.stop_loss:
            return True
        if self.side == "SHORT" and bar.high >= self.stop_loss:
            return True
        return False


@dataclass
class Trade:
    side: str
    entry_price: float
    exit_price: float
    quantity: float
    entry_time: datetime
    exit_time: datetime
    exit_reason: str

    @property
    def pnl(self) -> float:
        if self.side == "LONG":
            return (self.exit_price - self.entry_price) * self.quantity
        return (self.entry_price - self.exit_price) * self.quantity


class PaperEngine:
    """
    Simulates trade execution in paper mode.
    NOT connected to any broker.
    """

    DEFAULT_STOP_PCT = 0.005  # 0.5% stop from entry

    def __init__(self, default_quantity: float = 1.0) -> None:
        self.default_quantity = default_quantity
        self.position: Optional[Position] = None
        self.trades: List[Trade] = []
        self._order_counter = 0
        self._pending_order: Optional[Order] = None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def on_signal(self, signal: Signal, bar: Bar) -> Optional[Order]:
        """
        Submit an order based on the signal.
        Fills are executed on the NEXT bar's open via on_bar().
        """
        if signal == Signal.FLAT:
            return None

        if self._pending_order is not None:
            logger.debug("Ignoring signal — pending order exists")
            return None

        # Flip or enter
        if self.position is not None:
            if (signal == Signal.LONG and self.position.side == "LONG") or (
                signal == Signal.SHORT and self.position.side == "SHORT"
            ):
                return None  # already in the right direction
            self._close_position(bar.close, bar.timestamp, "signal_reversal")

        side = "BUY" if signal == Signal.LONG else "SELL"
        self._order_counter += 1
        order = Order(
            order_id=self._order_counter,
            side=side,
            quantity=self.default_quantity,
            submitted_at=bar.timestamp,
        )
        self._pending_order = order
        logger.info("Order submitted: %s qty=%.2f at %s", side, self.default_quantity, bar.timestamp)
        return order

    def on_bar(self, bar: Bar) -> float:
        """
        Process one bar: fill pending order, check stop-loss.
        Returns realized PnL for this bar.
        """
        realized_pnl = 0.0

        # Fill pending order at bar open (next-bar fill)
        if self._pending_order is not None:
            order = self._pending_order
            order.fill_price = bar.open
            order.filled_at = bar.timestamp
            self._pending_order = None

            side = "LONG" if order.side == "BUY" else "SHORT"
            stop = self._calc_stop(side, bar.open)
            self.position = Position(
                side=side,
                entry_price=bar.open,
                quantity=order.quantity,
                entry_time=bar.timestamp,
                stop_loss=stop,
            )
            logger.info(
                "Fill: %s @ %.4f  stop=%.4f  time=%s",
                side, bar.open, stop or 0, bar.timestamp,
            )

        # Check stop-loss on current position
        if self.position is not None and self.position.is_stopped(bar):
            exit_price = self.position.stop_loss  # fill at stop level
            realized_pnl = self._close_position(exit_price, bar.timestamp, "stop_loss")  # type: ignore[arg-type]

        return realized_pnl

    def close_all(self, price: float, timestamp: datetime) -> float:
        """Force-close any open position at the given price."""
        if self.position is None:
            return 0.0
        return self._close_position(price, timestamp, "end_of_session")

    def unrealized_pnl(self, current_price: float) -> float:
        if self.position is None:
            return 0.0
        return self.position.unrealized_pnl(current_price)

    def summary(self) -> dict:
        total_pnl = sum(t.pnl for t in self.trades)
        winners = [t for t in self.trades if t.pnl > 0]
        return {
            "total_trades": len(self.trades),
            "total_pnl": round(total_pnl, 2),
            "winners": len(winners),
            "losers": len(self.trades) - len(winners),
            "win_rate": round(len(winners) / len(self.trades), 3) if self.trades else 0.0,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _close_position(self, exit_price: float, timestamp: datetime, reason: str) -> float:
        if self.position is None:
            return 0.0
        trade = Trade(
            side=self.position.side,
            entry_price=self.position.entry_price,
            exit_price=exit_price,
            quantity=self.position.quantity,
            entry_time=self.position.entry_time,
            exit_time=timestamp,
            exit_reason=reason,
        )
        self.trades.append(trade)
        logger.info(
            "Closed %s @ %.4f  PnL=%.2f  reason=%s",
            trade.side, exit_price, trade.pnl, reason,
        )
        self.position = None
        return trade.pnl

    def _calc_stop(self, side: str, entry: float) -> float:
        if side == "LONG":
            return entry * (1 - self.DEFAULT_STOP_PCT)
        return entry * (1 + self.DEFAULT_STOP_PCT)
