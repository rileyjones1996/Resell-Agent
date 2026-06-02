"""
Trade and signal journal export — writes CSV and JSON to the export directory.

Trade journal columns:
  trade_id, side, entry_time, exit_time, entry_price, exit_price,
  quantity, pnl, exit_reason

Signal journal columns:
  timestamp, bar_close, signal, vwap, rsi, sma, trend,
  accepted, rejection_reason
"""
from __future__ import annotations

import csv
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.execution.paper_engine import Trade

logger = logging.getLogger(__name__)


@dataclass
class SignalRecord:
    timestamp: datetime
    bar_close: float
    signal: str
    vwap: float
    rsi: Optional[float]
    sma: Optional[float]
    trend: str
    accepted: bool
    rejection_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "bar_close": self.bar_close,
            "signal": self.signal,
            "vwap": round(self.vwap, 4),
            "rsi": round(self.rsi, 4) if self.rsi is not None else None,
            "sma": round(self.sma, 4) if self.sma is not None else None,
            "trend": self.trend,
            "accepted": self.accepted,
            "rejection_reason": self.rejection_reason,
        }


def _trade_to_dict(i: int, t: Trade) -> Dict[str, Any]:
    return {
        "trade_id": i + 1,
        "side": t.side,
        "entry_time": t.entry_time.isoformat(),
        "exit_time": t.exit_time.isoformat(),
        "entry_price": t.entry_price,
        "exit_price": t.exit_price,
        "quantity": t.quantity,
        "pnl": round(t.pnl, 4),
        "exit_reason": t.exit_reason,
    }


def export_trades(trades: List[Trade], export_dir: Path, run_label: str = "") -> None:
    """Write trades to trades_<label>.csv and trades_<label>.json."""
    if not trades:
        logger.info("No trades to export")
        return

    export_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"_{run_label}" if run_label else ""
    rows = [_trade_to_dict(i, t) for i, t in enumerate(trades)]

    csv_path = export_dir / f"trades{suffix}.csv"
    json_path = export_dir / f"trades{suffix}.json"

    with open(csv_path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    with open(json_path, "w") as fh:
        json.dump(rows, fh, indent=2)

    logger.info("Trade journal: %s (%d trades)", csv_path, len(trades))


def export_signals(
    signals: List[SignalRecord], export_dir: Path, run_label: str = ""
) -> None:
    """Write signal journal to signals_<label>.csv and signals_<label>.json."""
    if not signals:
        logger.info("No signals to export")
        return

    export_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"_{run_label}" if run_label else ""
    rows = [s.to_dict() for s in signals]

    csv_path = export_dir / f"signals{suffix}.csv"
    json_path = export_dir / f"signals{suffix}.json"

    with open(csv_path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    with open(json_path, "w") as fh:
        json.dump(rows, fh, indent=2)

    logger.info("Signal journal: %s (%d signals)", csv_path, len(signals))
