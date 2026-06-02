"""
Apex-style prop-firm risk manager.

Rules enforced:
  1. Max daily loss       — stops trading when realized + unrealized P&L < -limit
  2. Max trailing drawdown — tracks peak equity; stops if equity drops > limit from peak
  3. Max position size    — caps the dollar risk on any single trade
  4. Max trades per day   — hard cap on entry count per calendar day
  5. Trading halt         — once any rule is breached, no new entries are allowed
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from config.settings import RiskConfig

logger = logging.getLogger(__name__)


@dataclass
class RiskState:
    equity: float                       # current total equity
    peak_equity: float                  # highest equity seen since session start
    daily_realized_pnl: float = 0.0
    daily_unrealized_pnl: float = 0.0
    trades_today: int = 0
    trading_date: date = field(default_factory=date.today)
    halted: bool = False
    halt_reason: str = ""

    @property
    def total_daily_pnl(self) -> float:
        return self.daily_realized_pnl + self.daily_unrealized_pnl

    @property
    def drawdown_from_peak(self) -> float:
        return self.peak_equity - self.equity


class RiskManager:
    """
    Stateful risk manager.  Call update_equity() each bar, then
    check can_trade() before placing any order.
    """

    def __init__(self, config: RiskConfig) -> None:
        self.cfg = config
        self.state = RiskState(
            equity=config.account_size,
            peak_equity=config.account_size,
        )

    # ------------------------------------------------------------------
    # State updates
    # ------------------------------------------------------------------

    def update_equity(
        self,
        realized_pnl_delta: float = 0.0,
        unrealized_pnl: float = 0.0,
        trade_date: Optional[date] = None,
    ) -> None:
        """
        Call once per bar (or on fill).
        realized_pnl_delta — PnL from trades closed this bar.
        unrealized_pnl     — current open-position PnL.
        """
        today = trade_date or date.today()

        if today != self.state.trading_date:
            self._reset_daily(today)

        self.state.daily_realized_pnl += realized_pnl_delta
        self.state.daily_unrealized_pnl = unrealized_pnl
        self.state.equity = (
            self.cfg.account_size
            + self.state.daily_realized_pnl
            + self.state.daily_unrealized_pnl
        )

        if self.state.equity > self.state.peak_equity:
            self.state.peak_equity = self.state.equity

        self._check_rules()

    def record_trade(self) -> None:
        """Increment today's trade counter."""
        self.state.trades_today += 1

    # ------------------------------------------------------------------
    # Guard
    # ------------------------------------------------------------------

    def can_trade(self) -> bool:
        return not self.state.halted

    def position_size_ok(self, dollar_risk: float) -> bool:
        """Return True if the proposed risk is within limits."""
        return dollar_risk <= self.cfg.max_position_dollars

    def max_allowed_risk(self) -> float:
        return self.cfg.max_position_dollars

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _reset_daily(self, new_date: date) -> None:
        logger.info("New trading day: %s  (prev PnL: %.2f)", new_date, self.state.daily_realized_pnl)
        self.state.daily_realized_pnl = 0.0
        self.state.daily_unrealized_pnl = 0.0
        self.state.trades_today = 0
        self.state.trading_date = new_date
        # Note: halted state and peak_equity carry across days intentionally

    def _check_rules(self) -> None:
        if self.state.halted:
            return

        # Rule 1 — daily loss limit
        if self.state.total_daily_pnl <= -self.cfg.max_daily_loss_dollars:
            self._halt(
                f"Daily loss limit breached: {self.state.total_daily_pnl:.2f} "
                f"<= -{self.cfg.max_daily_loss_dollars:.2f}"
            )
            return

        # Rule 2 — trailing drawdown
        if self.state.drawdown_from_peak >= self.cfg.max_trailing_drawdown_dollars:
            self._halt(
                f"Trailing drawdown breached: {self.state.drawdown_from_peak:.2f} "
                f">= {self.cfg.max_trailing_drawdown_dollars:.2f} "
                f"(peak={self.state.peak_equity:.2f}, equity={self.state.equity:.2f})"
            )
            return

        # Rule 4 — max trades per day
        if self.state.trades_today >= self.cfg.max_trades_per_day:
            self._halt(
                f"Max daily trades reached: {self.state.trades_today} "
                f">= {self.cfg.max_trades_per_day}"
            )

    def _halt(self, reason: str) -> None:
        self.state.halted = True
        self.state.halt_reason = reason
        logger.warning("TRADING HALTED — %s", reason)
