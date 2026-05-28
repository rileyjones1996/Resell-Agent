"""Tests for the RiskManager."""
from __future__ import annotations

from datetime import date

import pytest

from config.settings import RiskConfig
from src.risk.risk_manager import RiskManager


@pytest.fixture
def cfg() -> RiskConfig:
    return RiskConfig(
        account_size=10_000.0,
        max_daily_loss_pct=0.03,        # $300
        max_trailing_drawdown_pct=0.05, # $500
        max_position_size_pct=0.02,     # $200
        max_trades_per_day=3,
    )


@pytest.fixture
def rm(cfg: RiskConfig) -> RiskManager:
    return RiskManager(cfg)


@pytest.fixture
def rm_dd() -> RiskManager:
    """Drawdown-focused fixture: daily loss limit is very high so only drawdown fires."""
    cfg = RiskConfig(
        account_size=10_000.0,
        max_daily_loss_pct=0.99,        # effectively unlimited daily loss
        max_trailing_drawdown_pct=0.05, # $500 trailing drawdown
        max_position_size_pct=0.02,
        max_trades_per_day=100,
    )
    return RiskManager(cfg)


class TestInitialState:
    def test_can_trade_initially(self, rm: RiskManager) -> None:
        assert rm.can_trade() is True

    def test_equity_equals_account_size(self, rm: RiskManager, cfg: RiskConfig) -> None:
        assert rm.state.equity == cfg.account_size

    def test_peak_equity_equals_account_size(self, rm: RiskManager, cfg: RiskConfig) -> None:
        assert rm.state.peak_equity == cfg.account_size


class TestDailyLossLimit:
    def test_halt_on_daily_loss_breach(self, rm: RiskManager, cfg: RiskConfig) -> None:
        rm.update_equity(realized_pnl_delta=-301.0)
        assert rm.state.halted is True
        assert "Daily loss" in rm.state.halt_reason

    def test_no_halt_under_limit(self, rm: RiskManager) -> None:
        rm.update_equity(realized_pnl_delta=-299.0)
        assert rm.state.halted is False

    def test_unrealized_counts_toward_daily_loss(self, rm: RiskManager) -> None:
        rm.update_equity(realized_pnl_delta=-100.0, unrealized_pnl=-201.0)
        assert rm.state.halted is True

    def test_no_new_trades_after_halt(self, rm: RiskManager) -> None:
        rm.update_equity(realized_pnl_delta=-400.0)
        assert rm.can_trade() is False


class TestTrailingDrawdown:
    def test_halt_on_drawdown_breach(self, rm_dd: RiskManager) -> None:
        # Grow equity to $11,000 (peak), then drop to $10,499 (drawdown=$501 > $500)
        rm_dd.update_equity(realized_pnl_delta=1000.0)
        assert rm_dd.state.peak_equity == pytest.approx(11_000.0)

        rm_dd.update_equity(realized_pnl_delta=-501.0)
        # cumulative daily pnl = +499, equity = 10_499, drawdown = 501 >= 500
        assert rm_dd.state.halted is True
        assert "drawdown" in rm_dd.state.halt_reason.lower()

    def test_no_halt_when_drawdown_within_limit(self, rm_dd: RiskManager) -> None:
        rm_dd.update_equity(realized_pnl_delta=1000.0)
        # drawdown = 11000 - (11000 - 499) = 499 < 500
        rm_dd.update_equity(realized_pnl_delta=-499.0)
        assert rm_dd.state.halted is False


class TestMaxTradesPerDay:
    def test_halt_at_trade_limit(self, rm: RiskManager) -> None:
        for _ in range(3):
            rm.record_trade()
        rm.update_equity()
        assert rm.state.halted is True

    def test_no_halt_below_limit(self, rm: RiskManager) -> None:
        for _ in range(2):
            rm.record_trade()
        rm.update_equity()
        assert rm.state.halted is False


class TestDailyReset:
    def test_daily_pnl_resets_on_new_date(self, rm: RiskManager) -> None:
        rm.update_equity(realized_pnl_delta=-100.0, trade_date=date(2024, 1, 15))
        assert rm.state.daily_realized_pnl == pytest.approx(-100.0)

        rm.update_equity(realized_pnl_delta=0.0, trade_date=date(2024, 1, 16))
        assert rm.state.daily_realized_pnl == pytest.approx(0.0)

    def test_trade_count_resets_on_new_date(self, rm: RiskManager) -> None:
        # Establish the date first, then record trades
        rm.update_equity(trade_date=date(2024, 1, 15))
        rm.record_trade()
        rm.record_trade()
        assert rm.state.trades_today == 2

        rm.update_equity(trade_date=date(2024, 1, 16))
        assert rm.state.trades_today == 0


class TestPositionSizing:
    def test_position_size_within_limit(self, rm: RiskManager) -> None:
        assert rm.position_size_ok(200.0) is True

    def test_position_size_over_limit(self, rm: RiskManager) -> None:
        assert rm.position_size_ok(200.01) is False

    def test_max_allowed_risk(self, rm: RiskManager, cfg: RiskConfig) -> None:
        assert rm.max_allowed_risk() == cfg.max_position_dollars
