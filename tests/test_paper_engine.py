"""Tests for the PaperEngine."""
from __future__ import annotations

from datetime import datetime

import pytest

from src.execution.paper_engine import PaperEngine
from src.feeds.market_data import Bar
from src.signals.strategy import Signal


def make_bar(
    ts: str = "2024-01-15 09:30",
    open_: float = 100.0,
    high: float = 102.0,
    low: float = 99.6,   # just above 0.5% stop of 100 → stop=99.5
    close: float = 101.0,
    volume: float = 1000.0,
) -> Bar:
    return Bar(
        timestamp=datetime.fromisoformat(ts),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


@pytest.fixture
def engine() -> PaperEngine:
    return PaperEngine(default_quantity=1.0)


class TestNoPosition:
    def test_flat_signal_produces_no_order(self, engine: PaperEngine) -> None:
        bar = make_bar()
        order = engine.on_signal(Signal.FLAT, bar)
        assert order is None

    def test_no_position_initially(self, engine: PaperEngine) -> None:
        assert engine.position is None

    def test_unrealized_pnl_zero_with_no_position(self, engine: PaperEngine) -> None:
        assert engine.unrealized_pnl(100.0) == pytest.approx(0.0)


class TestOrderFlow:
    def test_long_signal_creates_buy_order(self, engine: PaperEngine) -> None:
        bar = make_bar()
        order = engine.on_signal(Signal.LONG, bar)
        assert order is not None
        assert order.side == "BUY"

    def test_order_filled_on_next_bar_open(self, engine: PaperEngine) -> None:
        # Signal on bar1 → fill on bar2's open
        # bar2 must have low > stop (101.0 * 0.995 = 100.495)
        bar1 = make_bar("2024-01-15 09:30", open_=100.0)
        bar2 = make_bar("2024-01-15 09:31", open_=101.0, high=103.0, low=101.0, close=102.0)

        engine.on_signal(Signal.LONG, bar1)
        engine.on_bar(bar2)  # fills at bar2.open=101.0; low=101.0 > stop=100.495 ✓

        assert engine.position is not None
        assert engine.position.entry_price == pytest.approx(101.0)

    def test_second_signal_same_direction_ignored(self, engine: PaperEngine) -> None:
        bar1 = make_bar("2024-01-15 09:30", open_=100.0)
        bar2 = make_bar("2024-01-15 09:31", open_=101.0, high=103.0, low=101.0, close=102.0)

        engine.on_signal(Signal.LONG, bar1)
        engine.on_bar(bar2)  # fills

        order2 = engine.on_signal(Signal.LONG, bar2)  # already LONG
        assert order2 is None

    def test_short_signal_creates_sell_order(self, engine: PaperEngine) -> None:
        bar = make_bar()
        order = engine.on_signal(Signal.SHORT, bar)
        assert order is not None
        assert order.side == "SELL"


class TestStopLoss:
    def test_long_stopped_when_low_hits_stop(self, engine: PaperEngine) -> None:
        # Enter long at 100 (fill bar open); stop = 100 * 0.995 = 99.5
        bar1 = make_bar("2024-01-15 09:30", open_=100.0)
        engine.on_signal(Signal.LONG, bar1)

        fill_bar = make_bar("2024-01-15 09:31", open_=100.0, high=101.0, low=100.0)
        engine.on_bar(fill_bar)  # fills at 100; low=100.0 > 99.5 ✓ (no stop yet)

        stop_bar = make_bar("2024-01-15 09:32", open_=100.0, high=100.5, low=99.0)
        pnl = engine.on_bar(stop_bar)  # low=99.0 < 99.5 → stopped

        assert engine.position is None
        assert pnl < 0
        assert len(engine.trades) == 1
        assert engine.trades[0].exit_reason == "stop_loss"

    def test_short_stopped_when_high_hits_stop(self, engine: PaperEngine) -> None:
        # Enter short at 100; stop = 100 * 1.005 = 100.5
        bar1 = make_bar("2024-01-15 09:30", open_=100.0)
        engine.on_signal(Signal.SHORT, bar1)

        fill_bar = make_bar("2024-01-15 09:31", open_=100.0, high=100.0, low=99.0)
        engine.on_bar(fill_bar)  # fills at 100; high=100.0 < 100.5 ✓

        stop_bar = make_bar("2024-01-15 09:32", open_=100.2, high=101.0, low=100.0)
        pnl = engine.on_bar(stop_bar)  # high=101.0 > 100.5 → stopped

        assert engine.position is None
        assert pnl < 0
        assert engine.trades[0].exit_reason == "stop_loss"


class TestSummary:
    def test_summary_empty_when_no_trades(self, engine: PaperEngine) -> None:
        s = engine.summary()
        assert s["total_trades"] == 0
        assert s["total_pnl"] == 0.0
        assert s["win_rate"] == 0.0

    def test_close_all_records_trade(self, engine: PaperEngine) -> None:
        entry_bar = make_bar("2024-01-15 09:30", open_=100.0)
        engine.on_signal(Signal.LONG, entry_bar)

        # Fill bar: open=100, low=100 → stop=99.5 not triggered
        fill_bar = make_bar("2024-01-15 09:31", open_=100.0, high=102.0, low=100.0, close=101.0)
        engine.on_bar(fill_bar)

        engine.close_all(105.0, datetime.fromisoformat("2024-01-15 15:00"))
        s = engine.summary()
        assert s["total_trades"] == 1
        assert s["total_pnl"] == pytest.approx(5.0)
