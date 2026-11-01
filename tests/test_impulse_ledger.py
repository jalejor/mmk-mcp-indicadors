"""Round-2 layered ledger (re-buys, cross margin, liquidation) — synthetic, offline."""

from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from controllers.metrics.impulse_backtest import (
    BLOCK_IS,
    BLOCK_OOS,
    LayerSizing,
    LedgerConfig,
    PositionLedger,
    R_BASIS_EQUITY_PCT,
    ledger_metrics,
    simulate_ledger,
)

T0 = "2025-01-01T00:00:00+00:00"
T1 = "2025-01-02T00:00:00+00:00"


def test_single_layer_long_pnl_costs_and_r():
    led = PositionLedger(LedgerConfig())
    led.open(0, T0, "long", 100.0, 1000.0, invalidation=95.0)
    assert led.qty == pytest.approx(10.0)
    assert led.cash == pytest.approx(1300.0 - 1.5)  # 0.15% entry cost
    trade = led.close(5, T1, 110.0, "signal_exit")
    assert trade.pnl_gross_usdt == pytest.approx(100.0)
    assert trade.cost_usdt == pytest.approx(1.5 + 1.65)
    assert trade.pnl_net_usdt == pytest.approx(96.85)
    assert led.cash == pytest.approx(1396.85)
    assert trade.r_unit_usdt == pytest.approx(50.0)  # 10 units x 5 to the invalidation
    assert trade.r_net == pytest.approx(96.85 / 50.0)
    assert (trade.n_layers, trade.bars_held, trade.exit_reason) == (1, 5, "signal_exit")
    assert not led.is_open


def test_short_mirror():
    led = PositionLedger(LedgerConfig())
    led.open(0, T0, "short", 100.0, 1000.0, invalidation=104.0)
    trade = led.close(3, T1, 90.0, "signal_exit")
    assert trade.pnl_gross_usdt == pytest.approx(100.0)
    assert trade.r_unit_usdt == pytest.approx(40.0)


def test_layers_average_price_and_cost_per_layer():
    led = PositionLedger(LedgerConfig())
    led.open(0, T0, "long", 100.0, 1000.0, invalidation=90.0)
    led.add_layer(2, T0, 90.0, 1000.0)
    assert len(led.layers) == 2
    assert led.avg_price == pytest.approx(2000.0 / (10.0 + 1000.0 / 90.0))
    assert led.cash == pytest.approx(1300.0 - 3.0)  # E16 on each layer
    trade = led.close(4, T1, 100.0, "signal_exit")
    assert trade.n_layers == 2
    assert trade.pnl_gross_usdt == pytest.approx((1000.0 / 90.0) * 10.0)
    assert trade.r_unit_usdt == pytest.approx(100.0)  # layer 1 only: 10 x (100 - 90)


def test_leverage_cap_sizes_down_and_skips():
    led = PositionLedger(LedgerConfig(leverage=5.0))
    layer = led.open(0, T0, "long", 100.0, 10_000.0)
    assert layer.notional == pytest.approx(6500.0 / (1 + 5 * 0.0015))  # 5 x 1300, net of its cost
    assert led.add_layer(1, T0, 100.0, 1000.0) is None
    assert led.skipped_layers == 1
    assert led.exposure(100.0) <= 5.0 + 1e-9


def test_liquidation_price_and_close():
    led = PositionLedger(LedgerConfig(funding_rate_per_8h=0.0))
    led.open(0, T0, "long", 100.0, 6500.0)
    liq = led.liquidation_price()
    q = led.qty
    # at the liquidation price equity + uPnL == 0.5% x notional
    assert led.cash + q * (liq - 100.0) == pytest.approx(0.005 * q * liq)
    assert led.mark(1, T1, high=101.0, low=liq + 0.01, close=100.0, hours=4) is None
    trade = led.mark(2, T1, high=100.0, low=liq - 1.0, close=liq + 5.0, hours=4)
    assert trade is not None and trade.exit_reason == "liquidation"
    assert trade.exit_price == pytest.approx(liq)
    assert led.cash > 0 and not led.is_open
    assert ledger_metrics(led)["liquidations"] == 1


def test_short_liquidation_side():
    led = PositionLedger(LedgerConfig(funding_rate_per_8h=0.0))
    led.open(0, T0, "short", 100.0, 6500.0)
    liq = led.liquidation_price()
    assert liq > 100.0
    assert led.mark(1, T1, high=liq + 1.0, low=99.0, close=100.0, hours=4).exit_reason == "liquidation"


def test_funding_on_total_notional_per_8h():
    led = PositionLedger(LedgerConfig())
    led.open(0, T0, "long", 100.0, 1000.0)
    led.add_layer(1, T0, 100.0, 1000.0)
    cash = led.cash
    led.mark(2, T1, high=100.0, low=100.0, close=100.0, hours=8.0)
    assert cash - led.cash == pytest.approx(0.0001 * 2000.0)
    assert led.close(3, T1, 100.0, "x").funding_usdt == pytest.approx(0.2)


def test_r_basis_equity_pct():
    led = PositionLedger(LedgerConfig(r_basis=R_BASIS_EQUITY_PCT, r_equity_pct=1.0))
    led.open(0, T0, "long", 100.0, 1000.0)
    trade = led.close(1, T1, 101.3, "x")
    assert trade.r_unit_usdt == pytest.approx(1300.0 * 0.01)  # equity before the entry cost


def test_config_validation():
    with pytest.raises(ValueError):
        LedgerConfig(margin_mode="isolated")
    with pytest.raises(ValueError):
        LedgerConfig(r_basis="whatever")
    with pytest.raises(RuntimeError):
        PositionLedger().add_layer(0, T0, 100.0, 10.0)


# ---------------------------------------------------------------------------
# simulate_ledger: decisions -> ledger
# ---------------------------------------------------------------------------

def _df(n=20, start="2025-12-28"):
    index = pd.date_range(start, periods=n, freq="4h", tz="UTC")
    close = 100.0 + np.arange(n, dtype=float)
    return pd.DataFrame({"open": close, "high": close + 0.5, "low": close - 0.5, "close": close}, index=index)


def _ms(df, i):
    return int(df.index[i].value // 10**6)


def test_simulate_ledger_enter_add_exit_and_end_of_data():
    df = _df()
    decisions = [
        {"timestamp": _ms(df, 1), "action": "enter", "side": "long", "stop_price": 96.0, "confidence": 0.7,
         "reasons": ["bbwp_breakout_from_compression"]},
        {"timestamp": _ms(df, 2), "action": "alert", "side": "long"},
        {"timestamp": _ms(df, 3), "action": "add_layer", "side": "long"},
        {"timestamp": _ms(df, 4), "action": "hold", "side": "long"},
        {"timestamp": _ms(df, 6), "action": "exit", "side": "long", "exit_price": 105.5,
         "reasons": ["exit_rule_jeisson"]},
        {"timestamp": _ms(df, 15), "action": "enter", "side": "short", "stop_price": 120.0},
    ]
    start = datetime(2025, 12, 1, tzinfo=timezone.utc)
    end = datetime(2026, 2, 1, tzinfo=timezone.utc)
    split = datetime(2025, 12, 29, tzinfo=timezone.utc)
    res = simulate_ledger(df, decisions, split=split, start=start, end=end, timeframe="4h",
                          symbol="BTC/USDT", sizing=LayerSizing(risk_pct=0.75, add_notional_x=0.5))
    first, second = res["trades"]
    # layer 1: risk 0.75% of 1300 over a 5/101 stop distance
    assert first.layers[0]["notional"] == pytest.approx(1300 * 0.0075 / (5.0 / 101.0))
    assert first.layers[1]["notional"] == pytest.approx(0.5 * first.layers[0]["notional"])
    assert (first.n_layers, first.exit_reason, first.exit_price) == (2, "exit_rule_jeisson", 105.5)
    assert first.block == BLOCK_IS and first.reasons == ["bbwp_breakout_from_compression"]
    assert (second.side, second.exit_reason, second.block) == ("short", "end_of_data", BLOCK_OOS)
    assert res["decisions"]["alert"] == 1

    m = ledger_metrics(res["ledger"])
    assert m["n"] == 2 and m["avg_layers"] == 1.5
    assert m["equity_final"] == pytest.approx(1300 + m["pnl_total_usdt"], abs=0.02)
    assert set(m["exit_reasons"]) == {"exit_rule_jeisson", "end_of_data"}
    assert m["max_drawdown_equity_pct"] >= 0 and m["r_metrics"]["n"] == 2


def test_simulate_ledger_opposite_enter_closes_and_directions_filter():
    df = _df()
    decisions = [
        {"timestamp": _ms(df, 1), "action": "enter", "side": "long", "stop_price": 95.0},
        {"timestamp": _ms(df, 4), "action": "enter", "side": "short", "stop_price": 110.0},
    ]
    kw = dict(split=datetime(2026, 1, 1, tzinfo=timezone.utc), start=datetime(2025, 1, 1, tzinfo=timezone.utc),
              end=datetime(2027, 1, 1, tzinfo=timezone.utc), timeframe="4h")
    res = simulate_ledger(df, decisions, **kw)
    assert [t.exit_reason for t in res["trades"]] == ["opposite_signal"]
    only_short = simulate_ledger(df, decisions, directions=("short",), **kw)
    assert [t.side for t in only_short["trades"]] == ["short"]
