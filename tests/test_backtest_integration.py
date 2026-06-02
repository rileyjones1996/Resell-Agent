"""Integration tests — run the full backtest pipeline end-to-end."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import List, Tuple

import pytest

from backtest.runner import run_backtest


def make_csv(bars: List[Tuple], path: Path) -> Path:
    """Write a list of (ts, o, h, l, c, v) tuples to a CSV file."""
    with open(path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        writer.writerows(bars)
    return path


class TestBacktestPipeline:
    def test_runs_without_error_on_sample_csv(self) -> None:
        sample = Path("data/sample_ES_1min.csv")
        if not sample.exists():
            pytest.skip("sample CSV not present")
        result = run_backtest(sample, export=False)
        assert "total_trades" in result
        assert result["bars_processed"] == 30

    def test_zero_trades_on_monotone_rise(self, tmp_path: Path) -> None:
        # Rising prices → RSI climbs, never oversold → no LONG signal fires
        bars = [
            (f"2024-01-15 09:{30+i:02d}", 100+i, 101+i, 99+i, 100+i, 1000)
            for i in range(30)
        ]
        path = make_csv(bars, tmp_path / "rise.csv")
        result = run_backtest(path, export=False)
        assert result["total_trades"] == 0
        assert result["risk_halted"] is False

    def test_result_keys_present(self, tmp_path: Path) -> None:
        bars = [
            (f"2024-01-15 09:{30+i:02d}", 100, 101, 99, 100, 1000)
            for i in range(25)
        ]
        path = make_csv(bars, tmp_path / "flat.csv")
        result = run_backtest(path, export=False)
        for key in [
            "total_trades", "win_rate", "total_pnl", "profit_factor",
            "max_drawdown", "expectancy", "final_equity", "bars_processed",
            "signals_fired", "risk_halted",
        ]:
            assert key in result, f"Missing result key: {key}"

    def test_runner_no_error_when_export_false(self, tmp_path: Path) -> None:
        bars = [
            (f"2024-01-15 09:{30+i:02d}", 100, 101, 99, 100, 1000)
            for i in range(25)
        ]
        csv_path = make_csv(bars, tmp_path / "data.csv")
        result = run_backtest(csv_path, export=False)
        assert result is not None

    def test_no_new_trades_after_risk_halt(self, tmp_path: Path) -> None:
        """Verify RiskManager correctly blocks trades once halted."""
        from config.settings import RiskConfig
        from src.risk.risk_manager import RiskManager

        rm = RiskManager(RiskConfig(account_size=10_000, max_daily_loss_pct=0.03))
        rm._halt("pre-halted for test")
        assert rm.can_trade() is False

    def test_final_equity_without_trades(self, tmp_path: Path) -> None:
        bars = [
            (f"2024-01-15 09:{30+i:02d}", 100, 101, 99, 100, 1000)
            for i in range(25)
        ]
        path = make_csv(bars, tmp_path / "flat.csv")
        result = run_backtest(path, export=False)
        # No trades → equity stays at account_size
        from config.settings import CONFIG
        assert result["final_equity"] == pytest.approx(CONFIG.risk.account_size)
