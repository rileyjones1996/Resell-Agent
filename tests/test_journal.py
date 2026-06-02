"""Tests for backtest/journal.py — trade and signal export."""
from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

import pytest

from backtest.journal import SignalRecord, export_trades, export_signals
from src.execution.paper_engine import Trade


def make_trade(side: str = "LONG", entry: float = 100.0, exit_: float = 105.0) -> Trade:
    ts = datetime(2024, 1, 15, 9, 30)
    return Trade(
        side=side,
        entry_price=entry,
        exit_price=exit_,
        quantity=1.0,
        entry_time=ts,
        exit_time=datetime(2024, 1, 15, 10, 0),
        exit_reason="stop_loss",
    )


def make_signal(accepted: bool = True) -> SignalRecord:
    return SignalRecord(
        timestamp=datetime(2024, 1, 15, 9, 30),
        bar_close=100.0,
        signal="LONG",
        vwap=99.5,
        rsi=28.0,
        sma=98.0,
        trend="UP",
        accepted=accepted,
        rejection_reason="" if accepted else "pending_order_exists",
    )


class TestExportTrades:
    def test_csv_created(self, tmp_path: Path) -> None:
        export_trades([make_trade()], tmp_path)
        assert (tmp_path / "trades.csv").exists()

    def test_json_created(self, tmp_path: Path) -> None:
        export_trades([make_trade()], tmp_path)
        assert (tmp_path / "trades.json").exists()

    def test_csv_has_correct_columns(self, tmp_path: Path) -> None:
        export_trades([make_trade()], tmp_path)
        with open(tmp_path / "trades.csv") as fh:
            reader = csv.DictReader(fh)
            cols = set(reader.fieldnames or [])
        expected = {"trade_id", "side", "entry_time", "exit_time", "entry_price",
                    "exit_price", "quantity", "pnl", "exit_reason"}
        assert expected.issubset(cols)

    def test_pnl_correct_in_csv(self, tmp_path: Path) -> None:
        export_trades([make_trade("LONG", 100.0, 105.0)], tmp_path)
        with open(tmp_path / "trades.csv") as fh:
            rows = list(csv.DictReader(fh))
        assert float(rows[0]["pnl"]) == pytest.approx(5.0)

    def test_label_suffix_appended(self, tmp_path: Path) -> None:
        export_trades([make_trade()], tmp_path, run_label="test_run")
        assert (tmp_path / "trades_test_run.csv").exists()
        assert (tmp_path / "trades_test_run.json").exists()

    def test_empty_trades_writes_nothing(self, tmp_path: Path) -> None:
        export_trades([], tmp_path)
        assert not (tmp_path / "trades.csv").exists()

    def test_json_parseable(self, tmp_path: Path) -> None:
        export_trades([make_trade()], tmp_path)
        data = json.loads((tmp_path / "trades.json").read_text())
        assert isinstance(data, list)
        assert data[0]["trade_id"] == 1


class TestExportSignals:
    def test_csv_and_json_created(self, tmp_path: Path) -> None:
        export_signals([make_signal()], tmp_path)
        assert (tmp_path / "signals.csv").exists()
        assert (tmp_path / "signals.json").exists()

    def test_accepted_field_preserved(self, tmp_path: Path) -> None:
        export_signals([make_signal(accepted=True), make_signal(accepted=False)], tmp_path)
        with open(tmp_path / "signals.csv") as fh:
            rows = list(csv.DictReader(fh))
        assert rows[0]["accepted"] == "True"
        assert rows[1]["accepted"] == "False"

    def test_rejection_reason_preserved(self, tmp_path: Path) -> None:
        export_signals([make_signal(accepted=False)], tmp_path)
        data = json.loads((tmp_path / "signals.json").read_text())
        assert data[0]["rejection_reason"] == "pending_order_exists"

    def test_empty_signals_writes_nothing(self, tmp_path: Path) -> None:
        export_signals([], tmp_path)
        assert not (tmp_path / "signals.csv").exists()


class TestSignalRecord:
    def test_none_rsi_serializes_as_none(self) -> None:
        sig = SignalRecord(
            timestamp=datetime(2024, 1, 15, 9, 30),
            bar_close=100.0,
            signal="FLAT",
            vwap=100.0,
            rsi=None,
            sma=None,
            trend="NEUTRAL",
            accepted=False,
            rejection_reason="rsi_unavailable",
        )
        d = sig.to_dict()
        assert d["rsi"] is None
        assert d["sma"] is None
