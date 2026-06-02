"""
Central configuration — loads from .env then exposes typed settings.
All risk thresholds are expressed as fractions (0.03 = 3%).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root (two levels up from this file)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env", override=False)


def _float(key: str, default: float) -> float:
    return float(os.environ.get(key, default))


def _int(key: str, default: int) -> int:
    return int(os.environ.get(key, default))


def _bool(key: str, default: bool) -> bool:
    val = os.environ.get(key, str(default)).lower()
    return val in ("1", "true", "yes")


def _str(key: str, default: str) -> str:
    return os.environ.get(key, default)


@dataclass(frozen=True)
class RiskConfig:
    account_size: float = field(default_factory=lambda: _float("ACCOUNT_SIZE", 50_000.0))
    max_daily_loss_pct: float = field(default_factory=lambda: _float("MAX_DAILY_LOSS_PCT", 0.03))
    max_trailing_drawdown_pct: float = field(
        default_factory=lambda: _float("MAX_TRAILING_DRAWDOWN_PCT", 0.05)
    )
    max_position_size_pct: float = field(
        default_factory=lambda: _float("MAX_POSITION_SIZE_PCT", 0.02)
    )
    max_trades_per_day: int = field(default_factory=lambda: _int("MAX_TRADES_PER_DAY", 10))

    @property
    def max_daily_loss_dollars(self) -> float:
        return self.account_size * self.max_daily_loss_pct

    @property
    def max_trailing_drawdown_dollars(self) -> float:
        return self.account_size * self.max_trailing_drawdown_pct

    @property
    def max_position_dollars(self) -> float:
        return self.account_size * self.max_position_size_pct


@dataclass(frozen=True)
class StrategyConfig:
    rsi_period: int = field(default_factory=lambda: _int("RSI_PERIOD", 14))
    rsi_overbought: float = field(default_factory=lambda: _float("RSI_OVERBOUGHT", 70.0))
    rsi_oversold: float = field(default_factory=lambda: _float("RSI_OVERSOLD", 30.0))
    vwap_deviation_threshold: float = field(
        default_factory=lambda: _float("VWAP_DEVIATION_THRESHOLD", 0.001)
    )
    vwap_enabled: bool = field(default_factory=lambda: _bool("VWAP_ENABLED", True))
    sma_period: int = field(default_factory=lambda: _int("SMA_PERIOD", 20))
    stop_size_pct: float = field(default_factory=lambda: _float("STOP_SIZE_PCT", 0.005))


@dataclass(frozen=True)
class AppConfig:
    paper_mode: bool = field(default_factory=lambda: _bool("PAPER_MODE", True))
    data_dir: Path = field(
        default_factory=lambda: _PROJECT_ROOT / _str("DATA_DIR", "data")
    )
    log_dir: Path = field(
        default_factory=lambda: _PROJECT_ROOT / _str("LOG_DIR", "logs")
    )
    export_dir: Path = field(
        default_factory=lambda: _PROJECT_ROOT / _str("EXPORT_DIR", "exports")
    )
    log_level: str = field(default_factory=lambda: _str("LOG_LEVEL", "INFO"))
    risk: RiskConfig = field(default_factory=RiskConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)


# Singleton — import this everywhere
CONFIG = AppConfig()
