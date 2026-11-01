"""Round 4b (`impulse-2.2.0`, docs/impulsos-v2.md §R4): exit chain without phase_lost,
partial take on the ML RSI regime, structural invalidation on the guardian close,
guardian ML RSI contrary, isolated-margin ledger. Every expected number is derived
from the rule in the docstring, not from the code. Fixtures reuse the round-2
synthetic frames (4h trigger, 1d guardian) with the round-4b parameters applied
to the PRO profile so the arithmetic of S02 (N1 758.952, 1R 26) carries over.
"""

import numpy as np
import pandas as pd
import pytest

from controllers.metrics.impulse_backtest import LedgerConfig, PositionLedger
from controllers.metrics.impulse_sequential import (
    R4_OVERRIDES,
    SEQUENTIAL_PROFILES,
    SequentialMachine,
    r4_params,
    sequential_params,
)
from controllers.metrics.impulse_service import RULE_VERSION_R4, ImpulseParams
from test_impulse_sequential import GOLDEN_WINDOWS, N, _frames, _long_setup, _long_with_add, _verde_cross_up

T0 = "2025-01-01T00:00:00+00:00"
T1 = "2025-01-02T00:00:00+00:00"


def _p(**overrides):
    """PRO book (1300, 5x cross) + round-4b exits, golden windows W_f = 4."""
    return r4_params("pro", confirm_window_bars=dict(GOLDEN_WINDOWS), **overrides)


def _r4_frames(trigger, d1="bullish", w1="bullish", trig_regime="green", ctx_regime="gray"):
    """Round-2 frames + explicit ML RSI regime columns (trigger gate / guardian exit)."""
    frames = _frames(trigger, d1=d1, w1=w1)
    frames["4h"]["ml_rsi_regime"] = trig_regime
    frames["1d"]["ml_rsi_regime"] = ctx_regime
    return frames


def _run(frames, params=None):
    return SequentialMachine(params or _p(), frames).run()


# ---------------------------------------------------------------------------
# Params
# ---------------------------------------------------------------------------

def test_r4_params_snipper_book_and_exit_chain():
    p = r4_params("snipper")
    assert p.rule_version == RULE_VERSION_R4 == "impulse-2.2.0" and p.model == "sequential"
    assert (p.trigger_tf, p.confirm_tf, p.context_order()) == ("1h", "4h", ("4h", "1d"))
    assert (p.equity_usdt, p.leverage, p.margin_mode, p.maintenance_margin_rate) == (1700.0, 10.0, "isolated", 0.0056)
    assert p.confirm_window_bars == {"ao": 2, "adx": 5, "macd": 3, "rsi": 3}
    assert SequentialMachine(p, {"1h": _long_setup(8)}).ttl == 5
    assert p.phase_lost_exit is False and p.time_stop_bars is None and p.atr_mult_stop is None
    assert p.mlrsi_gate is True and p.partial_take_fraction == 0.5
    assert p.ctx_structural_exit is True and p.ctx_swing_back == 10 and p.ctx_mlrsi_exit is True and p.target_r is None
    # PRO keeps its own book under the same exit chain; 2.1.0 params are untouched
    pro = r4_params("pro")
    assert (pro.equity_usdt, pro.leverage, pro.margin_mode) == (1300.0, 5.0, "cross") and pro.phase_lost_exit is False
    r2 = sequential_params("pro")
    assert r2.rule_version == "impulse-2.1.0" and r2.phase_lost_exit is True and r2.time_stop_bars == 60
    assert r2.partial_take_fraction == 0.0 and r2.ctx_structural_exit is False and r2.ctx_mlrsi_exit is False
    assert "mlrsi_gate" not in SEQUENTIAL_PROFILES["snipper"]["book"] and set(R4_OVERRIDES) >= {"phase_lost_exit", "partial_take_fraction"}
    with pytest.raises(ValueError):
        ImpulseParams.sequential("pro", partial_take_fraction=1.0)
    with pytest.raises(ValueError):
        ImpulseParams.sequential("pro", target_r=0.0)


# ---------------------------------------------------------------------------
# Exits
# ---------------------------------------------------------------------------

def test_phase_lost_is_a_warning_not_an_exit_in_round_4b():
    """S10 setup: bbwp <= 50 from bar 16 and verde against from 18. 2.1.0 exits at 18
    (`exit_phase_lost`); 2.2.0 only emits `info_phase_lost` and stays IN_POSITION."""
    t = _long_setup(N)
    bbwp = t["bbwp"].to_numpy().copy()
    bbwp[16:] = 45.0
    t["bbwp"] = bbwp
    verde = _verde_cross_up(10, N)
    verde[18:] = -5.0
    t["konkorde_verde"] = verde
    d = _run(_r4_frames(t))
    assert d[12].action == "enter" and d[12].rule_version == "impulse-2.2.0"
    assert d[18].action == "hold" and "info_phase_lost" in d[18].reasons and "exit_phase_lost" not in d[18].reasons
    assert d[N - 1].state == "in_position"  # no time stop either (None)
    # the 2.1.0 regression still exits (same frames, round-2 params)
    r2 = SequentialMachine(sequential_params("pro", confirm_window_bars=dict(GOLDEN_WINDOWS)), _frames(t)).run()
    assert r2[18].action == "exit" and "exit_phase_lost" in r2[18].reasons


def test_jeisson_rule_still_exits_everything():
    """S08 under 2.2.0: red turn at 20 (92 -> 80) + verde zero cross down at 22 -> exit at 22 with both layers."""
    t = _long_with_add(N)
    bbwp = t["bbwp"].to_numpy().copy()
    bbwp[18:20] = 92.0
    bbwp[20:] = 80.0
    t["bbwp"] = bbwp
    verde = _verde_cross_up(10, N)
    verde[22:] = -5.0
    t["konkorde_verde"] = verde
    d = _run(_r4_frames(t))
    assert d[15].action == "add_layer"
    x = d[22]
    assert x.action == "exit" and len(x.layers) == 2 and {"exit_rule_jeisson", "exit_bbwp_red_turn"} <= set(x.reasons)


def test_partial_take_once_on_regime_leaving_the_colour():
    """Long entered at 12 (regime green). Green -> gray on 16: close 50 % of every layer at close[16]
    (`reduce`), 1R unchanged (26), layer qty halves; a later green -> gray does NOT take again;
    the add after the take still scales from the ORIGINAL layer-1 notional (0.5 x 758.952)."""
    t = _long_with_add(N, add_bar=20)
    regime = ["green"] * 16 + ["gray"] * 2 + ["green"] * 4 + ["gray"] * (N - 22)
    frames = _r4_frames(t)
    frames["4h"]["ml_rsi_regime"] = regime
    d = _run(frames)
    e = d[12]
    assert e.action == "enter" and e.notional == pytest.approx(758.952, abs=1e-3)
    qty1 = e.layers[0]["qty"]
    r = d[16]
    assert r.action == "reduce" and {"partial_take_mlrsi", "mlrsi_green_to_gray"} <= set(r.reasons)
    assert r.layers[0]["qty"] == pytest.approx(qty1 / 2) and r.notional == pytest.approx(qty1 / 2 * 61300.0, abs=1e-3)
    assert r.one_r_usdt == pytest.approx(26.0, abs=1e-3) and r.exit_price == 61300.0 and r.state == "in_position"
    assert d[17].action == "hold" and d[17].context["partial_taken"] is True
    a = d[20]  # RSI cross 50 up at 20, regime green -> add allowed, sized from the original layer 1
    assert a.action == "add_layer" and a.notional == pytest.approx(0.5 * 758.952, abs=1e-3)
    assert d[22].action != "reduce"  # second green -> gray: no second take
    # entry candle never takes, and a 2.1.0 run never reduces
    assert all(x.action != "reduce" for x in SequentialMachine(sequential_params("pro", confirm_window_bars=dict(GOLDEN_WINDOWS)), frames).run())


def test_structural_invalidation_guardian_swing_and_guardian_close():
    """Guardian (1d) lows at 58000 over the last 10 closed daily candles -> inv = 58000
    (`invalidation_ctx_swing`, wider than range 59200 and ATR 59800). 1R = 2 % x 1300 = 26 at
    dist 3300 -> N1 = 26 x 61300 / 3300 = 482.97. A 4h close at 57000 (bars 14-16) does NOT exit:
    the daily candle aligned to those bars is the entry's own (closed 01-12 00:00). The daily
    candle of 2026-01-12 (closes 01-13 00:00 = close of 4h bar 17) closes at 57500 <= 58000 ->
    exit on bar 17 at the 4h close (`exit_invalidation_ctx_close`)."""
    t = _long_setup(N)
    close = t["close"].to_numpy().copy()
    close[14:] = 57000.0
    t["close"], t["high"], t["low"] = close, close + 100.0, close - 100.0
    t.loc[t.index[5], "low"] = 59200.0
    frames = _r4_frames(t)
    g = frames["1d"]
    g["low"] = 58000.0
    e = _run(frames)[12]
    assert (e.invalidation_price, e.invalidation_source) == (58000.0, "invalidation_ctx_swing")
    assert e.notional == pytest.approx(26.0 * 61300 / 3300, abs=1e-2) and e.one_r_usdt == pytest.approx(26.0, abs=1e-3)
    d = _run(frames)
    assert d[16].action == "hold" and "hold_beyond_invalidation_awaiting_ctx_close" in d[16].reasons
    g.loc[g.index == pd.Timestamp("2026-01-12", tz="UTC"), "close"] = 57500.0
    d = _run(frames)
    assert [x.action for x in d[14:17]] == ["hold", "hold", "hold"]
    x = d[17]
    assert x.action == "exit" and {"exit_invalidation", "exit_invalidation_ctx_close"} <= set(x.reasons) and x.exit_price == 57000.0
    # a guardian close that merely wicks through (close 58500 > 58000) keeps the trade
    g.loc[g.index == pd.Timestamp("2026-01-12", tz="UTC"), ["close", "low"]] = [58500.0, 57000.0]
    assert _run(frames)[17].action == "hold"


def test_guardian_mlrsi_contrary_exits_and_blocks_entry_gray_does_not():
    """Long open; guardian regime red on the daily candle of 2026-01-12 -> exit on bar 17
    (`exit_ctx_mlrsi_against`). Gray on the guardian never exits. A guardian already red at
    the entry candle blocks the ENTER (`ctx_mlrsi_against`)."""
    t = _long_setup(N)
    frames = _r4_frames(t)
    g = frames["1d"]
    regime = pd.Series("gray", index=g.index)
    regime[g.index >= pd.Timestamp("2026-01-12", tz="UTC")] = "red"
    g["ml_rsi_regime"] = regime
    d = _run(frames)
    assert d[12].action == "enter" and d[16].action == "hold"
    assert d[17].action == "exit" and {"exit_ctx_mlrsi_against", "ctx_mlrsi_red"} <= set(d[17].reasons)
    g["ml_rsi_regime"] = "gray"
    assert _run(frames)[N - 1].state == "in_position"
    g["ml_rsi_regime"] = "red"
    blocked = _run(frames)[12]
    assert blocked.action == "alert" and "ctx_mlrsi_against" in blocked.reasons
    g["ml_rsi_regime"] = "green"  # favourable guardian: no effect
    assert _run(frames)[12].action == "enter"


def test_optional_target_r_off_by_default_and_fires_when_set():
    t = _long_with_add(N, add_bar=15, add_close=66000.0)  # +4700 on 0.012381 qty = +58.2 USDT = 2.24 R at bar 15
    assert _run(_r4_frames(t))[15].action != "exit"
    d = _run(_r4_frames(t), _p(target_r=2.0))
    assert d[15].action == "exit" and "exit_target_r" in d[15].reasons


# ---------------------------------------------------------------------------
# Ledger: isolated margin and partial takes
# ---------------------------------------------------------------------------

def test_isolated_liquidation_uses_only_the_position_margin():
    """1700 USDT, 10x isolated, mmr 0.56 %. Long 1000 notional at 100 -> qty 10, margin 100.
    liq = (q a - margin) / (q (1 - m)) = 900 / 9.944 = 90.507 (9.5 % below entry; cross would be
    (1000 - 1698.5) / 9.944 < 0 = unreachable). A wick to 90.0 liquidates at 90.507: the trade
    loses the whole margin plus fees and nothing else (cash = 1700 - 1.5 entry - 100 margin -
    exit cost 0.15 % x 905.07 = 1.358)."""
    cfg = LedgerConfig(initial_equity=1700.0, leverage=10.0, margin_mode="isolated", maintenance_rate=0.0056)
    led = PositionLedger(cfg)
    led.open(0, T0, "long", 100.0, 1000.0, invalidation=95.0)
    assert led.liquidation_price() == pytest.approx(900.0 / (10.0 * (1.0 - 0.0056)), abs=1e-6)
    assert led.liquidation_price() == pytest.approx(90.507, abs=1e-3)
    assert led.mark(1, T1, high=101.0, low=95.0, close=96.0, hours=1.0) is None
    trade = led.mark(2, T1, high=96.0, low=90.0, close=91.0, hours=1.0)
    assert trade is not None and trade.exit_reason == "liquidation" and trade.exit_price == pytest.approx(90.507, abs=1e-3)
    funding = cfg.funding_rate_per_8h / 8.0 * 10.0 * (96.0 + 91.0)  # 1 h per mark, on the notional at each close
    assert led.cash == pytest.approx(1700.0 - 1.5 - 100.0 - 0.0015 * 10.0 * trade.exit_price - funding, abs=1e-3)
    assert not led.is_open
    # short mirror: liq = (margin + q a) / (q (1 + m)) = 1100 / 10.056 = 109.387
    led2 = PositionLedger(cfg)
    led2.open(0, T0, "short", 100.0, 1000.0, invalidation=105.0)
    assert led2.liquidation_price() == pytest.approx(1100.0 / (10.0 * 1.0056), abs=1e-6)
    with pytest.raises(ValueError):
        LedgerConfig(margin_mode="portfolio")


def test_partial_take_realises_half_and_keeps_the_r_unit():
    """Long 1000 at 100 (qty 10, inv 95 -> 1R = 50). reduce 50 % at 110: gross +50, exit cost
    0.15 % x 550 = 0.825; layers keep qty 5; 1R stays 50 (layer-1 ORIGINAL qty). Close at 120:
    gross on the rest 5 x 20 = 100 -> trade gross 150, cost 1.5 + 0.825 + 0.15 % x 600 = 3.225."""
    led = PositionLedger(LedgerConfig())
    led.open(0, T0, "long", 100.0, 1000.0, invalidation=95.0)
    take = led.reduce(2, T0, 110.0, 0.5)
    assert take["qty"] == pytest.approx(5.0) and take["pnl_gross_usdt"] == pytest.approx(50.0) and take["cost_usdt"] == pytest.approx(0.825)
    assert led.qty == pytest.approx(5.0) and led.cash == pytest.approx(1300.0 - 1.5 + 50.0 - 0.825)
    assert led.r_unit() == pytest.approx(50.0)
    trade = led.close(4, T1, 120.0, "signal_exit")
    assert trade.pnl_gross_usdt == pytest.approx(150.0) and trade.cost_usdt == pytest.approx(3.225)
    assert trade.pnl_net_usdt == pytest.approx(150.0 - 3.225) and trade.r_net == pytest.approx((150.0 - 3.225) / 50.0)
    assert len(trade.partial_takes) == 1 and trade.partial_takes[0]["price"] == 110.0
    with pytest.raises(RuntimeError):
        led.reduce(5, T1, 100.0, 0.5)
