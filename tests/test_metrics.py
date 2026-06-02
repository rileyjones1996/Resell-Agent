"""Tests for backtest/metrics.py"""
from __future__ import annotations

from datetime import datetime

import pytest

from backtest.metrics import compute_metrics
from src.execution.paper_engine import Trade


def make_trade(side: str, entry: float, exit_: float, qty: float = 1.0) -> Trade:
    ts = datetime(2024, 1, 15, 9, 30)
    return Trade(
        side=side,
        entry_price=entry,
        exit_price=exit_,
        quantity=qty,
        entry_time=ts,
        exit_time=ts,
        exit_reason="test",
    )


class TestEmptyTrades:
    def test_all_zeros_with_no_trades(self) -> None:
        m = compute_metrics([], starting_equity=10_000.0)
        assert m["total_trades"] == 0
        assert m["total_pnl"] == 0.0
        assert m["win_rate"] == 0.0
        assert m["avg_win"] is None
        assert m["avg_loss"] is None
        assert m["profit_factor"] is None
        assert m["max_drawdown"] == 0.0
        assert m["expectancy"] == 0.0

    def test_halt_reason_passed_through(self) -> None:
        m = compute_metrics([], starting_equity=10_000.0, halt_reason="daily_loss")
        assert m["halt_reason"] == "daily_loss"


class TestWinRate:
    def test_all_winners(self) -> None:
        trades = [make_trade("LONG", 100.0, 102.0) for _ in range(3)]
        m = compute_metrics(trades, 10_000.0)
        assert m["win_rate"] == pytest.approx(1.0)
        assert m["losers"] == 0

    def test_all_losers(self) -> None:
        trades = [make_trade("LONG", 102.0, 100.0) for _ in range(3)]
        m = compute_metrics(trades, 10_000.0)
        assert m["win_rate"] == pytest.approx(0.0)
        assert m["winners"] == 0

    def test_mixed(self) -> None:
        trades = [
            make_trade("LONG", 100.0, 102.0),   # +2
            make_trade("LONG", 100.0, 99.0),    # -1
        ]
        m = compute_metrics(trades, 10_000.0)
        assert m["win_rate"] == pytest.approx(0.5)
        assert m["total_pnl"] == pytest.approx(1.0)


class TestProfitFactor:
    def test_profit_factor_no_losses(self) -> None:
        trades = [make_trade("LONG", 100.0, 105.0)]
        m = compute_metrics(trades, 10_000.0)
        assert m["profit_factor"] is None  # no losses to divide by

    def test_profit_factor_computed(self) -> None:
        trades = [
            make_trade("LONG", 100.0, 104.0),   # +4
            make_trade("LONG", 100.0, 98.0),    # -2
        ]
        m = compute_metrics(trades, 10_000.0)
        assert m["profit_factor"] == pytest.approx(2.0)

    def test_profit_factor_below_one_losing_system(self) -> None:
        trades = [
            make_trade("LONG", 100.0, 101.0),   # +1
            make_trade("LONG", 100.0, 97.0),    # -3
        ]
        m = compute_metrics(trades, 10_000.0)
        assert m["profit_factor"] == pytest.approx(1 / 3, abs=5e-4)


class TestMaxDrawdown:
    def test_no_drawdown_with_all_winners(self) -> None:
        trades = [make_trade("LONG", 100.0, 102.0) for _ in range(3)]
        m = compute_metrics(trades, 10_000.0)
        assert m["max_drawdown"] == pytest.approx(0.0)

    def test_drawdown_after_peak(self) -> None:
        # equity goes 10000 → 10005 → 10003 → 10008 → 10001
        trades = [
            make_trade("LONG", 100.0, 105.0),   # +5
            make_trade("LONG", 100.0, 98.0),    # -2  (drawdown=2)
            make_trade("LONG", 100.0, 105.0),   # +5
            make_trade("LONG", 100.0, 93.0),    # -7  (drawdown=7)
        ]
        m = compute_metrics(trades, 10_000.0)
        assert m["max_drawdown"] == pytest.approx(7.0)

    def test_drawdown_with_short_trades(self) -> None:
        trades = [
            make_trade("SHORT", 100.0, 95.0),   # +5
            make_trade("SHORT", 100.0, 103.0),  # -3
        ]
        m = compute_metrics(trades, 10_000.0)
        assert m["max_drawdown"] == pytest.approx(3.0)


class TestExpectancy:
    def test_positive_expectancy(self) -> None:
        # 2 wins of +10, 1 loss of -3 → win_rate=2/3, avg_win=10, avg_loss=-3
        # expectancy = (2/3 * 10) + (1/3 * -3) = 6.667 - 1 = 5.667
        trades = [
            make_trade("LONG", 100.0, 110.0),
            make_trade("LONG", 100.0, 110.0),
            make_trade("LONG", 100.0, 97.0),
        ]
        m = compute_metrics(trades, 10_000.0)
        assert m["expectancy"] == pytest.approx((2/3 * 10) + (1/3 * -3), rel=1e-3)

    def test_zero_expectancy_no_trades(self) -> None:
        m = compute_metrics([], 10_000.0)
        assert m["expectancy"] == 0.0


class TestAvgWinLoss:
    def test_avg_win(self) -> None:
        trades = [
            make_trade("LONG", 100.0, 106.0),  # +6
            make_trade("LONG", 100.0, 102.0),  # +2
        ]
        m = compute_metrics(trades, 10_000.0)
        assert m["avg_win"] == pytest.approx(4.0)

    def test_avg_loss(self) -> None:
        trades = [
            make_trade("LONG", 100.0, 98.0),   # -2
            make_trade("LONG", 100.0, 96.0),   # -4
        ]
        m = compute_metrics(trades, 10_000.0)
        assert m["avg_loss"] == pytest.approx(-3.0)

    def test_short_trade_pnl_sign(self) -> None:
        t = make_trade("SHORT", 100.0, 95.0)  # short: profit = 100-95 = +5
        assert t.pnl == pytest.approx(5.0)
        t2 = make_trade("SHORT", 100.0, 105.0)  # short: loss = 100-105 = -5
        assert t2.pnl == pytest.approx(-5.0)
