"""Tests for the VWAP strategy."""
from __future__ import annotations

from datetime import datetime

import pytest

from config.settings import StrategyConfig
from src.feeds.market_data import Bar
from src.signals.strategy import Signal, VWAPStrategy, _calc_rsi, _calc_sma


def make_bar(
    ts: str,
    open_: float,
    high: float,
    low: float,
    close: float,
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
def cfg() -> StrategyConfig:
    return StrategyConfig(
        rsi_period=3,
        rsi_overbought=70.0,
        rsi_oversold=30.0,
        vwap_deviation_threshold=0.001,
    )


@pytest.fixture
def strat(cfg: StrategyConfig) -> VWAPStrategy:
    return VWAPStrategy(cfg)


class TestRSICalc:
    def test_returns_none_with_insufficient_data(self) -> None:
        assert _calc_rsi([100.0, 101.0], period=3) is None

    def test_all_gains_returns_100(self) -> None:
        closes = [100.0, 101.0, 102.0, 103.0]
        rsi = _calc_rsi(closes, period=3)
        assert rsi == pytest.approx(100.0)

    def test_all_losses_returns_0(self) -> None:
        closes = [103.0, 102.0, 101.0, 100.0]
        rsi = _calc_rsi(closes, period=3)
        assert rsi == pytest.approx(0.0)

    def test_mixed_returns_expected_value(self) -> None:
        # [100, 101, 100, 101]: deltas=[-,-,+] → gains=[0,0,1], losses=[0,1,0]
        # Wait, last 3 deltas from period=3, series=[100,101,100,101]:
        # deltas = [+1, -1, +1]; gains=[1,0,1], losses=[0,1,0]
        # avg_gain=2/3, avg_loss=1/3, RS=2, RSI=66.67
        closes = [100.0, 101.0, 100.0, 101.0]
        rsi = _calc_rsi(closes, period=3)
        assert rsi is not None
        assert rsi == pytest.approx(200 / 3, rel=1e-3)  # ≈ 66.67


class TestSMACalc:
    def test_returns_none_with_insufficient_data(self) -> None:
        assert _calc_sma([100.0], period=3) is None

    def test_correct_average(self) -> None:
        assert _calc_sma([1.0, 2.0, 3.0], period=3) == pytest.approx(2.0)

    def test_uses_last_n_only(self) -> None:
        assert _calc_sma([1.0, 2.0, 3.0, 4.0, 5.0], period=3) == pytest.approx(4.0)


class TestVWAPReset:
    def test_vwap_resets_on_new_day(self, strat: VWAPStrategy) -> None:
        bar1 = make_bar("2024-01-15 09:30", 100, 101, 99, 100, volume=1000)
        bar2 = make_bar("2024-01-15 09:31", 200, 201, 199, 200, volume=1000)
        # Use a close that gives a different VWAP than bar2's day-VWAP (150)
        bar3 = make_bar("2024-01-16 09:30", 120, 122, 118, 120, volume=1000)

        strat.on_bar(bar1)
        a2 = strat.on_bar(bar2)
        a3 = strat.on_bar(bar3)

        # Bar3's VWAP should equal its own typical price (only bar on day 2)
        expected_tp3 = (122 + 118 + 120) / 3  # = 120.0
        assert a3.vwap == pytest.approx(expected_tp3)
        # Bar2's day-VWAP = 150, bar3's day-VWAP = 120 — they differ
        assert a2.vwap != pytest.approx(a3.vwap)


class TestSignalGeneration:
    def test_flat_when_rsi_unavailable(self, strat: VWAPStrategy) -> None:
        bar = make_bar("2024-01-15 09:30", 100, 101, 99, 100)
        analysis = strat.on_bar(bar)
        assert analysis.signal == Signal.FLAT
        assert analysis.rsi is None

    def test_placeholders_are_none(self, strat: VWAPStrategy) -> None:
        bar = make_bar("2024-01-15 09:30", 100, 101, 99, 100)
        analysis = strat.on_bar(bar)
        assert analysis.key_level is None
        assert analysis.order_flow is None

    def test_trend_neutral_insufficient_data(self, strat: VWAPStrategy) -> None:
        bar = make_bar("2024-01-15 09:30", 100, 101, 99, 100)
        analysis = strat.on_bar(bar)
        assert analysis.trend == "NEUTRAL"

    def test_trend_up_above_sma(self, strat: VWAPStrategy) -> None:
        # 22 bars of rising prices so close > 20-bar SMA
        bars = [
            make_bar(f"2024-01-15 09:{30+i:02d}", 100 + i, 101 + i, 99 + i, 100 + i)
            for i in range(22)
        ]
        analyses = [strat.on_bar(b) for b in bars]
        last = analyses[-1]
        assert last.trend == "UP"
