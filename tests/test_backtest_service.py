"""Backtest engine tests.

We avoid hitting any real exchange by monkeypatching `_load_history` with a
deterministic synthetic OHLCV DataFrame that nevertheless exercises every
branch of the engine (entries, target hits, stop hits and end-of-data exits).
"""

from datetime import datetime, timedelta, timezone
from typing import List

import numpy as np
import pandas as pd
import pytest

from controllers.metrics import backtest_service as bs_module
from controllers.metrics.backtest_service import BacktestService


def _synthetic_history(n: int = 600, seed: int = 1) -> pd.DataFrame:
    """Generate OHLCV with enough volatility for the rule engine to trigger."""
    rng = np.random.default_rng(seed)
    # Random walk with mild drift so we get both up- and down-trending phases.
    returns = rng.normal(loc=0.0005, scale=0.02, size=n)
    close = 30000.0 * np.cumprod(1 + returns)
    open_ = np.concatenate([[close[0]], close[:-1]])
    high = np.maximum(open_, close) * (1 + rng.uniform(0.001, 0.01, size=n))
    low = np.minimum(open_, close) * (1 - rng.uniform(0.001, 0.01, size=n))
    volume = rng.uniform(50, 500, size=n)
    idx = pd.date_range("2025-01-01", periods=n, freq="h", tz="UTC")
    df = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )
    df.index.name = "datetime"
    return df


def _make_service(monkeypatch, df: pd.DataFrame, **kwargs) -> BacktestService:
    start = df.index[150].to_pydatetime()
    end = df.index[-1].to_pydatetime() + timedelta(seconds=1)
    defaults = dict(
        symbol="BTC/USDT",
        timeframe="1h",
        exchange="binance",
        start=start,
        end=end,
        initial_capital=10000.0,
        risk_per_trade_pct=1.5,
        warmup_bars=120,
    )
    defaults.update(kwargs)
    svc = BacktestService(**defaults)
    monkeypatch.setattr(svc, "_load_history", lambda: df)
    return svc


def test_backtest_runs_without_error(monkeypatch):
    df = _synthetic_history()
    svc = _make_service(monkeypatch, df)
    result = svc.run()
    assert result["symbol"] == "BTC/USDT"
    assert "equity_curve" in result
    assert "trades" in result
    assert isinstance(result["total_trades"], int)
    assert result["initial_capital"] == 10000.0
    assert isinstance(result["final_equity"], float)


def test_backtest_no_peek_ahead(monkeypatch):
    """IndicatorsService should only ever see data up to and including bar i."""
    df = _synthetic_history(n=400, seed=3)
    seen_lengths: List[int] = []
    real_init = bs_module.IndicatorsService.__init__

    def spy_init(self, df_in, **kwargs):  # type: ignore[no-untyped-def]
        seen_lengths.append(len(df_in))
        return real_init(self, df_in, **kwargs)

    monkeypatch.setattr(bs_module.IndicatorsService, "__init__", spy_init)
    svc = _make_service(monkeypatch, df)
    svc.run()

    assert seen_lengths, "IndicatorsService was never invoked"
    # The final slice cannot exceed the total number of bars.
    assert max(seen_lengths) <= len(df)
    # Lengths must be monotonically non-decreasing (no future leak).
    assert seen_lengths == sorted(seen_lengths)


def test_backtest_metrics_consistency(monkeypatch):
    df = _synthetic_history(n=500, seed=7)
    svc = _make_service(monkeypatch, df)
    result = svc.run()
    sum_trade_pnl = sum(t["pnl_dollars"] for t in result["trades"])
    assert result["total_pnl_dollars"] == pytest.approx(sum_trade_pnl, abs=0.01)
    final_equity = result["equity_curve"][-1]["equity"] if result["equity_curve"] else result["initial_capital"]
    assert final_equity == pytest.approx(result["initial_capital"] + sum_trade_pnl, abs=0.5)


def test_backtest_no_overlapping_trades(monkeypatch):
    df = _synthetic_history(n=500, seed=11)
    svc = _make_service(monkeypatch, df, max_concurrent_positions=1)
    result = svc.run()

    # Walk through trades sorted by entry time and assert they don't overlap
    # with `max_concurrent_positions` open at any point.
    trades = sorted(
        result["trades"],
        key=lambda t: t["entry_time"] or "",
    )
    open_count = 0
    events = []
    for t in trades:
        if t["entry_time"]:
            events.append((t["entry_time"], 1))
        if t["exit_time"]:
            events.append((t["exit_time"], -1))
    events.sort()
    for _, delta in events:
        open_count += delta
        assert open_count <= svc.max_concurrent_positions
        assert open_count >= 0
