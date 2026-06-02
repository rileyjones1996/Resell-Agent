"""
Market data feed — reads OHLCV bars from a CSV file.

Expected CSV columns (case-insensitive):
    timestamp, open, high, low, close, volume
"""
from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Generator, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Bar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    @property
    def typical_price(self) -> float:
        return (self.high + self.low + self.close) / 3.0


class CSVMarketFeed:
    """Yields Bar objects from a CSV file one bar at a time (like a live feed)."""

    REQUIRED_COLS = {"timestamp", "open", "high", "low", "close", "volume"}

    def __init__(self, csv_path: Path) -> None:
        self.csv_path = csv_path
        self._bars: Optional[List[Bar]] = None

    def _load(self) -> List[Bar]:
        if not self.csv_path.exists():
            raise FileNotFoundError(f"CSV not found: {self.csv_path}")

        bars: List[Bar] = []
        with open(self.csv_path, newline="") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames is None:
                raise ValueError("CSV has no headers")

            headers = {h.strip().lower() for h in reader.fieldnames}
            missing = self.REQUIRED_COLS - headers
            if missing:
                raise ValueError(f"CSV missing columns: {missing}")

            for row in reader:
                r = {k.strip().lower(): v.strip() for k, v in row.items()}
                try:
                    ts = datetime.fromisoformat(r["timestamp"])
                except ValueError:
                    ts = datetime.strptime(r["timestamp"], "%Y-%m-%d %H:%M")

                bars.append(
                    Bar(
                        timestamp=ts,
                        open=float(r["open"]),
                        high=float(r["high"]),
                        low=float(r["low"]),
                        close=float(r["close"]),
                        volume=float(r["volume"]),
                    )
                )

        logger.info("Loaded %d bars from %s", len(bars), self.csv_path)
        return bars

    def bars(self) -> Generator[Bar, None, None]:
        if self._bars is None:
            self._bars = self._load()
        yield from self._bars

    def all_bars(self) -> List[Bar]:
        if self._bars is None:
            self._bars = self._load()
        return list(self._bars)
