"""
Signal generation strategy.

Indicators:
  - VWAP  (volume-weighted average price, resets each day)
  - RSI   (relative strength index)
  - Trend filter (price above/below N-bar SMA)
  - Key level placeholder  (returns None until implemented)
  - Order-flow placeholder (returns None until implemented)

Signal logic:
  LONG  when: price > VWAP + threshold AND RSI < oversold AND trend is UP
  SHORT when: price < VWAP - threshold AND RSI > overbought AND trend is DOWN
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import List, Optional

from src.feeds.market_data import Bar
from config.settings import StrategyConfig

logger = logging.getLogger(__name__)


class Signal(Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    FLAT = "FLAT"


@dataclass
class BarAnalysis:
    bar: Bar
    vwap: float
    rsi: Optional[float]
    sma: Optional[float]
    trend: str          # "UP", "DOWN", "NEUTRAL"
    signal: Signal
    key_level: None     # placeholder
    order_flow: None    # placeholder


def _calc_rsi(closes: List[float], period: int) -> Optional[float]:
    if len(closes) < period + 1:
        return None
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(d, 0.0) for d in deltas[-period:]]
    losses = [abs(min(d, 0.0)) for d in deltas[-period:]]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0.0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _calc_sma(closes: List[float], period: int) -> Optional[float]:
    if len(closes) < period:
        return None
    return sum(closes[-period:]) / period


class VWAPStrategy:
    """
    Stateful strategy that processes bars one at a time.
    VWAP resets at the start of each calendar day.
    """

    def __init__(self, config: StrategyConfig) -> None:
        self.cfg = config
        self._cum_tp_vol: float = 0.0
        self._cum_vol: float = 0.0
        self._vwap_date: Optional[date] = None
        self._closes: List[float] = []

    def on_bar(self, bar: Bar) -> BarAnalysis:
        bar_date = bar.timestamp.date()

        # Reset VWAP at start of each day
        if bar_date != self._vwap_date:
            self._cum_tp_vol = 0.0
            self._cum_vol = 0.0
            self._vwap_date = bar_date

        self._cum_tp_vol += bar.typical_price * bar.volume
        self._cum_vol += bar.volume
        vwap = self._cum_tp_vol / self._cum_vol if self._cum_vol > 0 else bar.close

        self._closes.append(bar.close)

        rsi = _calc_rsi(self._closes, self.cfg.rsi_period)
        sma = _calc_sma(self._closes, self.cfg.sma_period)
        trend = self._trend(bar.close, sma)
        signal = self._signal(bar.close, vwap, rsi, trend)

        return BarAnalysis(
            bar=bar,
            vwap=vwap,
            rsi=rsi,
            sma=sma,
            trend=trend,
            signal=signal,
            key_level=None,
            order_flow=None,
        )

    def _trend(self, close: float, sma: Optional[float]) -> str:
        if sma is None:
            return "NEUTRAL"
        if close > sma:
            return "UP"
        if close < sma:
            return "DOWN"
        return "NEUTRAL"

    def _signal(
        self,
        close: float,
        vwap: float,
        rsi: Optional[float],
        trend: str,
    ) -> Signal:
        if rsi is None:
            return Signal.FLAT

        threshold = vwap * self.cfg.vwap_deviation_threshold

        long_ok = (
            close > vwap + threshold
            and rsi < self.cfg.rsi_oversold
            and trend == "UP"
        )
        short_ok = (
            close < vwap - threshold
            and rsi > self.cfg.rsi_overbought
            and trend == "DOWN"
        )

        if long_ok:
            return Signal.LONG
        if short_ok:
            return Signal.SHORT
        return Signal.FLAT

    # Placeholders — return None until real data sources are wired in
    @staticmethod
    def key_level_near(price: float) -> None:  # noqa: ARG004
        """Returns key S/R level if price is within range, else None."""
        return None

    @staticmethod
    def order_flow_bias() -> None:
        """Returns order-flow directional bias, or None if unavailable."""
        return None
