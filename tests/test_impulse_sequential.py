"""Round-2 sequential machine goldens (docs/impulsos-v2.md §R2, cases S01-S11 + mechanics).

Every expected number below is derived from the RULE in the docstring of the
test, not from running the code (spec §R2.i). Frames are indicator COLUMNS of
closed candles with timestamps so the 1d / 1w guardian aligns per §e. Golden
params: every follower window W_f = 4 (-> alert_ttl = 4), E0 = 1300 USDT.
"""

import numpy as np
import pandas as pd
import pytest

from controllers.metrics.impulse_sequential import (
    FITTED_WINDOWS,
    SequentialMachine,
    sequential_params,
)
from controllers.metrics.impulse_service import ImpulseEngine, ImpulseParams

N = 30
GOLDEN_WINDOWS = {"ao": 4, "adx": 4, "macd": 4, "rsi": 4}


def _params(**overrides):
    return ImpulseParams.sequential("pro", confirm_window_bars=dict(GOLDEN_WINDOWS), **overrides)


def _trigger(n=N, start="2026-01-10", **cols) -> pd.DataFrame:
    """Flat 4h frame: no event anywhere unless a column is overridden."""
    index = pd.date_range(start, periods=n, freq="4h", tz="UTC")
    close = np.full(n, 60000.0)
    base = {
        "close": close, "high": close + 100.0, "low": close - 100.0, "bbwp": np.full(n, 60.0),
        "konkorde_marron": 50.0, "konkorde_media": np.full(n, 5.0), "konkorde_verde": np.full(n, 10.0),
        "konkorde_azul": 1.0, "adx14": 20.0, "plus_di": 20.0, "minus_di": 20.0, "ao": np.zeros(n),
        "macd": np.zeros(n), "macd_signal": np.zeros(n), "rsi14": np.full(n, 50.0), "atr14": np.full(n, 500.0),
    }
    for k, v in cols.items():
        base[k] = np.asarray(v, dtype=float) if not isinstance(v, (int, float)) else v
    df = pd.DataFrame(base, index=index)
    if "high" not in cols:
        df["high"] = df["close"] + 100.0
    if "low" not in cols:
        df["low"] = df["close"] - 100.0
    return df


def _ctx(tf: str, bias: str, n: int, start: str) -> pd.DataFrame:
    """§e score = 3 sign(verde) + 2 sign(di) + 2 sign(ao) + 1 sign(macd - signal); |score| >= 3 -> bias."""
    index = pd.date_range(start, periods=n, freq={"1d": "D", "1w": "7D"}[tf], tz="UTC")
    s = {"bullish": 1.0, "bearish": -1.0}.get(bias, 0.0)
    if bias == "neutral":  # verde +3, di -2, ao -2, macd +1 = 0
        cols = {"konkorde_verde": 10.0, "plus_di": 15.0, "minus_di": 25.0, "ao": -100.0, "macd": 10.0, "macd_signal": 5.0}
    else:
        cols = {"konkorde_verde": 10.0 * s, "plus_di": 20 + 5 * s, "minus_di": 20 - 5 * s, "ao": 100.0 * s,
                "macd": 10.0 * s, "macd_signal": 5.0 * s}
    close = np.full(n, 60000.0)
    return pd.DataFrame({"close": close, "high": close + 500, "low": close - 500, "bbwp": 55.0,
                         "konkorde_marron": 50.0, "konkorde_media": 5.0, "konkorde_azul": 1.0, "adx14": 25.0,
                         "atr14": 1500.0, **cols}, index=index)


def _frames(trigger: pd.DataFrame, d1="bullish", w1="bullish"):
    return {"4h": trigger, "1d": _ctx("1d", d1, 45, "2025-12-15"), "1w": _ctx("1w", w1, 14, "2025-11-03")}


def _verde_cross_up(at: int, n=N) -> np.ndarray:
    v = np.full(n, -5.0)
    v[at:] = 5.0
    return v


def _step_series(n, before, after, at):
    v = np.full(n, float(before))
    v[at:] = float(after)
    return v


def _run(frames, params=None, warmup=0):
    return SequentialMachine(params or _params(), frames).run(warmup=warmup)


def _long_setup(n=N):
    """S02 worked example (spec §R2.c): leader verde zero cross up at bar 10, AO zero
    cross up at 11, MACD cross up at 12 -> ENTER long at 12 on close 61300; lows
    carry a 59200 swing low inside [a-9, e] so the range invalidation (59200) is
    wider than close - 3 ATR (61300 - 1500 = 59800)."""
    close = np.full(n, 60000.0)
    close[12:] = 61300.0
    low = close - 100.0
    low[5] = 59200.0
    ao = np.zeros(n)
    ao[11:] = 50.0
    macd = np.zeros(n)
    macd[12:] = 20.0
    return _trigger(n, close=close, low=low, konkorde_verde=_verde_cross_up(10, n), ao=ao, macd=macd,
                    macd_signal=np.full(n, 10.0))


# ---------------------------------------------------------------------------
# Params / wiring
# ---------------------------------------------------------------------------

def test_sequential_params_carry_the_frozen_windows_and_rule_doc():
    p = ImpulseParams.sequential("pro")
    assert p.model == "sequential" and p.confirm_window_bars == FITTED_WINDOWS["pro"] == {"ao": 2, "adx": 4, "macd": 3, "rsi": 2}
    assert (p.trigger_tf, p.confirm_tf, p.context_order()) == ("4h", "1d", ("1d", "1w"))
    assert (p.equity_usdt, p.leverage, p.margin_mode) == (1300.0, 5.0, "cross")
    assert (p.layer1_risk_pct, p.layer1_max_exposure_x, p.layer_add_scale, p.max_layers) == (2.0, 1.5, 0.5, 3)
    assert (p.max_open_risk_pct, p.max_exposure_x, p.invalidation_atr_mult, p.invalidation_range_back) == (6.0, 3.0, 3.0, 9)
    assert p.atr_mult_stop is None and p.time_stop_bars == 60 and p.n_confirm == 2
    d1 = sequential_params("pro_1d")
    assert (d1.trigger_tf, d1.confirm_tf, d1.confirm_window_bars) == ("1d", "1w", {"ao": 3, "adx": 3, "macd": 2, "rsi": 5})
    assert SequentialMachine(d1, {"1d": _trigger(5)}).ttl == 5
    with pytest.raises(ValueError):
        sequential_params("whale")
    with pytest.raises(ValueError):
        ImpulseParams(model="committee")
    with pytest.raises(ValueError):
        ImpulseParams(model="sequential", confirm_window_bars={"volume": 3})
    assert ImpulseParams.for_profile("pro").model == "vote"  # round-1 path untouched


def test_engine_dispatches_replay_and_evaluate_to_the_machine():
    frames = _frames(_long_setup())
    decisions = ImpulseEngine(_params()).replay(frames, warmup=0)
    assert len(decisions) == N and decisions[12].action == "enter"
    last = ImpulseEngine(_params()).evaluate(frames)
    assert last.state == "in_position" and "state" in last.to_dict() and last.to_dict()["layers"]


# ---------------------------------------------------------------------------
# S01-S04: alerts and entries
# ---------------------------------------------------------------------------

def test_s01_alert_without_confirmation_expires_after_ttl():
    d = _run(_frames(_trigger(konkorde_verde=_verde_cross_up(10))))
    assert d[9].action == "none" and d[9].state == "flat" and "no_leader" in d[9].reasons
    a = d[10]
    assert (a.action, a.state, a.alert_side, a.alert_age) == ("alert", "alert", "long", 0)
    assert "konkorde_verde_zero_cross_up" in a.reasons and "alert_waiting_confirmation" in a.reasons
    assert d[14].state == "alert" and d[14].alert_age == 4  # a + ttl is still alive
    assert d[15].state == "flat" and "alert_expired" in d[15].reasons and d[15].action == "none"


def test_s02_enter_long_konkorde_leader_worked_example():
    """N1 = min(0.02 x 1300 x 61300 / 2100, 1.5 x 1300) = 758.952 USDT; 1R = 26.00 USDT."""
    d = _run(_frames(_long_setup()))
    assert d[11].action == "alert" and d[11].confirmations == {"ao": {"side": 1, "bar": 11, "event": "ao_zero_cross_up"}}
    e = d[12]
    assert (e.action, e.side, e.state) == ("enter", "long", "in_position")
    assert e.notional == pytest.approx(758.952, abs=1e-3)
    assert e.one_r_usdt == pytest.approx(26.0, abs=1e-3)
    assert (e.invalidation_price, e.invalidation_source) == (59200.0, "invalidation_range")
    assert e.stop_price == 59200.0 and set(e.confirmations) == {"ao", "macd"}
    assert {"confirm_ao:ao_zero_cross_up", "confirm_macd:macd_cross_up", "invalidation_range", "context_aligned"} <= set(e.reasons)
    assert e.layers[0]["price"] == 61300.0 and e.exposure_x == pytest.approx(758.952 / 1300, abs=1e-3)
    assert e.confidence == pytest.approx(0.5)  # 2 of 4 families
    assert e.liquidation_price is None  # notional 759 < equity 1300: a long cannot be liquidated (§R2.f "null when unreachable")


def test_s02b_invalidation_takes_the_atr_level_when_it_is_wider():
    """Same setup, swing low 60500 -> range 60500 vs ATR 61300 - 1500 = 59800: ATR wins."""
    t = _long_setup()
    t.loc[t.index[5], "low"] = 60500.0
    e = _run(_frames(t))[12]
    assert (e.invalidation_price, e.invalidation_source) == (59800.0, "invalidation_atr")
    assert e.one_r_usdt == pytest.approx(26.0, abs=1e-3)  # 1R is always 2% E0 when the cap does not bind
    assert e.notional == pytest.approx(26.0 * 61300 / 1500, abs=1e-2)


def test_s02c_layer1_exposure_cap_binds_on_a_tight_invalidation():
    """Swing low 61000 -> dist 300 -> risk sizing 26 x 61300 / 300 = 5312 > 1.5 x 1300 = 1950: cap; 1R = 1950/61300 x 300 = 9.54."""
    t = _long_setup()
    t.loc[t.index[5], "low"] = 60000.0  # other lows are 59900 (close - 100) ... make all lows >= 61000 in window
    t["low"] = np.where(np.arange(N) >= 1, 61000.0, t["low"])
    t["atr14"] = 50.0  # ATR level 61150 -> range 61000 wider
    e = _run(_frames(t))[12]
    assert e.invalidation_price == 61000.0
    assert e.notional == pytest.approx(1950.0)
    assert e.one_r_usdt == pytest.approx(1950.0 / 61300 * 300, abs=1e-3)


def test_s03_enter_short_from_bbwp_ignition_side_from_followers_range_invalidation():
    """bbwp 20 ... 45 -> 55 at bar 10 (min of last 10 <= 30: ignition, side undecided); bar 11: AO zero
    cross down + MACD cross down (unanimous short) -> side_from_follower, 2 confirmations, bbwp 60 in
    (50, 90), 1d bearish -> ENTER short at 11 on 61000; max high in [1, 11] = 64000 > 61000 + 1500."""
    n = N
    bbwp = np.full(n, 20.0)
    bbwp[9] = 45.0
    bbwp[10] = 55.0
    bbwp[11:] = 60.0
    close = np.full(n, 61000.0)
    high = close + 100.0
    high[4] = 64000.0
    ao = np.zeros(n)
    ao[11:] = -50.0
    macd = np.zeros(n)
    macd[11:] = -20.0
    t = _trigger(n, bbwp=bbwp, close=close, high=high, ao=ao, macd=macd, macd_signal=np.full(n, -10.0))
    d = _run(_frames(t, d1="bearish", w1="bearish"))
    assert d[10].action == "alert" and d[10].alert_side == "none" and "bbwp_ignition" in d[10].reasons
    assert "alert_side_undecided" in d[10].reasons
    e = d[11]
    assert (e.action, e.side) == ("enter", "short") and "side_from_follower" in e.reasons
    assert (e.invalidation_price, e.invalidation_source) == (64000.0, "invalidation_range")
    assert e.notional == pytest.approx(26.0 * 61000 / 3000, abs=1e-3)
    assert e.phase == "ignition"


def test_s04_confirmation_outside_its_window_does_not_count_and_the_alert_expires():
    """Leader at 10, AO at 11 (counts), MACD at 15 = a + 5 > W = 4 -> not a confirmation; bar 15 > a + ttl -> expired."""
    n = N
    ao = np.zeros(n)
    ao[11:] = 50.0
    macd = np.zeros(n)
    macd[15:] = 20.0
    t = _trigger(n, konkorde_verde=_verde_cross_up(10), ao=ao, macd=macd, macd_signal=np.full(n, 10.0))
    d = _run(_frames(t))
    assert d[14].state == "alert" and set(d[14].confirmations) == {"ao"}
    assert d[15].state == "flat" and "alert_expired" in d[15].reasons and d[15].action == "none"


def test_alert_cancelled_by_two_contrary_families_and_replaced_by_opposite_leader():
    n = N
    ao = np.zeros(n)
    ao[11:] = -50.0  # AO zero cross DOWN against a long alert
    macd = np.zeros(n)
    macd[11:] = -20.0  # MACD cross down
    t = _trigger(n, konkorde_verde=_verde_cross_up(10), ao=ao, macd=macd, macd_signal=np.full(n, -10.0))
    d = _run(_frames(t))
    assert d[11].state == "flat" and "alert_cancelled_contrary" in d[11].reasons
    verde = _verde_cross_up(10, n)
    verde[13:] = -5.0  # opposite leader (zero cross down) at bar 13
    d = _run(_frames(_trigger(n, konkorde_verde=verde)))
    assert d[13].alert_side == "short" and d[13].alert_age == 0 and "alert_replaced_opposite_leader" in d[13].reasons


def test_entry_gates_bbwp_regime_exhaustion_and_context():
    t = _long_setup()
    t["bbwp"] = 45.0
    d = _run(_frames(t))
    assert d[12].action == "alert" and "entry_wait_bbwp_regime" in d[12].reasons
    t["bbwp"] = 92.0
    assert "entry_blocked_exhaustion" in _run(_frames(t))[12].reasons
    t["bbwp"] = 60.0
    assert "context_against" in _run(_frames(t, d1="bearish"))[12].reasons
    neutral = _run(_frames(t, d1="neutral"))[12]
    assert neutral.action == "enter" and "context_neutral" in neutral.reasons
    missing = _run({"4h": t})[12]
    assert missing.action == "alert" and "context_missing" in missing.reasons


# ---------------------------------------------------------------------------
# S05-S07: re-buys
# ---------------------------------------------------------------------------

def _long_with_add(n=N, add_bar=15, add_close=63000.0):
    """S05: after S02 (entry bar 12), RSI crosses 50 up at `add_bar` with close 63000:
    N2 = 0.5 x 758.952 = 379.476; avg = 1138.43 / (0.0123810 + 0.0060234) = 61856.38;
    open_risk = 26.00 + 0.0060234 x 3800 = 48.89 (3.76% E0); exposure 0.0184044 x 63000 / 1300 = 0.892."""
    t = _long_setup(n)
    close = t["close"].to_numpy().copy()
    close[add_bar:] = add_close
    t["close"], t["high"], t["low"] = close, close + 100.0, close - 100.0
    t.loc[t.index[5], "low"] = 59200.0
    rsi = np.full(n, 50.0)
    rsi[add_bar:] = 55.0
    t["rsi14"] = rsi
    return t


def test_s05_valid_rebuy_worked_example():
    d = _run(_frames(_long_with_add()))
    a = d[15]
    assert a.action == "add_layer" and a.notional == pytest.approx(379.476, abs=1e-3)
    assert len(a.layers) == 2 and a.avg_entry == pytest.approx(61856.38, abs=0.05)
    assert a.open_risk_usdt == pytest.approx(48.89, abs=0.01)
    assert a.exposure_x == pytest.approx(0.892, abs=0.002)
    assert a.invalidation_price == 59200.0 and a.one_r_usdt == pytest.approx(26.0, abs=1e-3)  # unchanged
    assert {"add_layer_follower_confirm", "rsi_cross_50_up"} <= set(a.reasons)
    assert d[13].action == "hold" and "hold_no_follower_confirm" in d[13].reasons


def test_s06_rebuy_rejected_max_layers_and_min_gap():
    """Layer 1 at 12; RSI cross-50-up at 15 and 18 -> layers 2 and 3 (max_layers = 3 INCLUDES layer 1);
    the RSI cross at 21 is rejected (max layers). An AO slope turn up at 16 (ao 50 -> 60 after a flat
    stretch) is a same-side follower only 1 candle after layer 2 -> rejected by the 3-candle gap."""
    n = 40
    t = _long_with_add(n, add_bar=15)
    rsi = np.full(n, 50.0)
    for bar in (15, 18, 21):
        rsi[bar] = 55.0  # cross 50 up on each of these bars (back to 50 in between)
    t["rsi14"] = rsi
    ao = t["ao"].to_numpy().copy()
    ao[16] = 60.0
    t["ao"] = ao
    d = _run(_frames(t))
    assert [d[b].action for b in (15, 16, 18, 21)] == ["add_layer", "hold", "add_layer", "hold"]
    assert "add_rejected_min_gap" in d[16].reasons and "add_rejected_max_layers" in d[21].reasons
    assert len(d[21].layers) == 3 and d[17].action == "hold" and "hold_follower_against" in d[17].reasons


def test_s07_rebuy_rejected_not_in_profit_phase_and_context():
    t = _long_with_add(add_close=61000.0)  # below the 61300 entry
    assert "add_rejected_not_in_profit" in _run(_frames(t))[15].reasons
    t = _long_with_add()
    t.loc[t.index[15], "bbwp"] = 45.0  # contraction, not ignition/expansion
    assert "add_rejected_phase" in _run(_frames(t))[15].reasons
    t = _long_with_add()
    frames = _frames(t, d1="bullish")
    frames["1d"].loc[:, ["konkorde_verde", "ao", "macd", "macd_signal"]] = [-10.0, -100.0, -10.0, -5.0]
    frames["1d"].loc[:, ["plus_di", "minus_di"]] = [15.0, 25.0]  # 1d turns bearish for the whole frame
    d = _run(frames)
    assert d[12].action == "alert" and "context_against" in d[12].reasons  # the entry itself is blocked


def test_rebuy_risk_cap_six_percent_of_e0():
    """Adds on a far-away price: layer 2 at 70000 -> qty 379.476 / 70000 x (70000 - 59200) = 58.5 USDT risk,
    26 + 58.5 = 84.5 > 78 (6% of 1300) -> add_rejected_risk_cap."""
    t = _long_with_add(add_close=70000.0)
    a = _run(_frames(t))[15]
    assert a.action == "hold" and "add_rejected_risk_cap" in a.reasons and len(a.layers) == 1


# ---------------------------------------------------------------------------
# S08-S10: exits
# ---------------------------------------------------------------------------

def test_s08_full_jeisson_exit_with_two_layers_inside_the_3_candle_window():
    """Red turn at bar 20 (bbwp 92 -> 80, drop 12 >= 8) and verde zero cross down at bar 22 (window [20, 22], one leg
    on 22) -> exit at the close of bar 22 (62000) with both layers; a cross on bar 23 would be outside."""
    n = N
    t = _long_with_add(n)
    bbwp = t["bbwp"].to_numpy().copy()
    bbwp[18:20] = 92.0
    bbwp[20:] = 80.0
    t["bbwp"] = bbwp
    verde = _verde_cross_up(10, n)
    verde[22:] = -5.0
    t["konkorde_verde"] = verde
    close = t["close"].to_numpy().copy()
    close[22:] = 62000.0
    t["close"], t["high"], t["low"] = close, close + 100.0, close - 100.0
    t.loc[t.index[5], "low"] = 59200.0
    d = _run(_frames(t))
    assert d[20].action == "hold" and "hold_exit_incomplete" in d[20].reasons
    x = d[22]
    assert x.action == "exit" and x.exit_price == 62000.0 and len(x.layers) == 2
    assert {"exit_rule_jeisson", "exit_bbwp_red_turn", "exit_konkorde_zero_cross_against"} <= set(x.reasons)
    assert d[23].state == "flat"
    # same bars but the cross on 23: the drop left the window -> no Jeisson exit
    verde = _verde_cross_up(10, n)
    verde[23:] = -5.0
    t["konkorde_verde"] = verde
    d = _run(_frames(t))
    assert d[23].action != "exit" or "exit_rule_jeisson" not in d[23].reasons


def test_no_same_candle_flip_leader_on_the_exit_candle_is_ignored():
    n = N
    t = _long_with_add(n)
    bbwp = t["bbwp"].to_numpy().copy()
    bbwp[21] = 92.0
    bbwp[22:] = 80.0
    t["bbwp"] = bbwp
    verde = _verde_cross_up(10, n)
    verde[22:] = -5.0  # zero cross down on 22 = exit leg AND a short leader
    t["konkorde_verde"] = verde
    d = _run(_frames(t))
    assert d[22].action == "exit"
    assert d[22].state == "flat" and d[23].state == "flat" and "no_leader" in d[23].reasons


def test_s09_wide_invalidation_exit_short_on_close_not_wick():
    n = N
    bbwp = np.full(n, 20.0)
    bbwp[9], bbwp[10] = 45.0, 55.0
    bbwp[11:] = 60.0
    close = np.full(n, 61000.0)
    high = close + 100.0
    high[4] = 64000.0
    high[15] = 64500.0  # wick through the invalidation: must NOT exit
    close[16:] = 64000.0  # close at the invalidation -> exit
    ao = np.zeros(n)
    ao[11:] = -50.0
    macd = np.zeros(n)
    macd[11:] = -20.0
    t = _trigger(n, bbwp=bbwp, close=close, high=high, low=close - 100.0, ao=ao, macd=macd, macd_signal=np.full(n, -10.0))
    d = _run(_frames(t, d1="bearish", w1="bearish"))
    assert d[11].action == "enter" and d[11].side == "short" and d[11].invalidation_price == 64000.0
    assert d[15].action == "hold"
    assert d[16].action == "exit" and "exit_invalidation" in d[16].reasons and d[16].exit_price == 64000.0


def test_s10_phase_lost_suppressed_while_verde_favours_then_exits_when_it_turns():
    n = N
    t = _long_setup(n)
    bbwp = t["bbwp"].to_numpy().copy()
    bbwp[16:] = 45.0  # <= 50 from bar 16
    t["bbwp"] = bbwp
    verde = _verde_cross_up(10, n)
    verde[18:] = -5.0  # verde against from 18
    t["konkorde_verde"] = verde
    d = _run(_frames(t))
    assert d[16].action == "hold" and "phase_lost_suppressed_verde_favor" in d[16].reasons
    assert d[17].action == "hold"
    assert d[18].action == "exit" and "exit_phase_lost" in d[18].reasons


def test_time_stop_after_60_candles_below_half_r():
    n = 80
    t = _long_setup(n)
    d = _run(_frames(t))
    assert d[71].action == "hold"
    assert d[72].action == "exit" and "exit_time_stop" in d[72].reasons  # entry 12 + 60


# ---------------------------------------------------------------------------
# S11: ML RSI gate (H2) + mechanics
# ---------------------------------------------------------------------------

def test_s11_mlrsi_gate_gray_blocks_green_allows_red_is_against():
    t = _long_setup()
    for regime, expect in (("gray", "mlrsi_gate_gray"), ("red", "mlrsi_gate_against")):
        t["ml_rsi_regime"] = regime
        e = _run(_frames(t), _params(mlrsi_gate=True))[12]
        assert e.action == "alert" and expect in e.reasons and e.mlrsi_regime == regime
    t["ml_rsi_regime"] = "green"
    e = _run(_frames(t), _params(mlrsi_gate=True))[12]
    assert e.action == "enter" and "mlrsi_green" in e.reasons
    # the gate never forces an exit and blocks re-buys when the regime leaves the side
    t = _long_with_add()
    t["ml_rsi_regime"] = ["green"] * 15 + ["gray"] * (N - 15)
    d = _run(_frames(t), _params(mlrsi_gate=True))
    assert d[12].action == "enter" and d[15].action == "hold" and "add_rejected_mlrsi" in d[15].reasons
    assert d[16].state == "in_position"
    # H1 ignores the column
    assert _run(_frames(t))[15].action == "add_layer"


def test_equity_feed_scales_layer_one_and_force_enter_anchors_a_trade():
    m = SequentialMachine(_params(), _frames(_long_setup()))
    for i in range(12):
        m.step(i)
    e = m.step(12, equity=2600.0)
    assert e.notional == pytest.approx(2 * 758.952, abs=1e-2) and e.one_r_usdt == pytest.approx(52.0, abs=1e-3)
    m2 = SequentialMachine(_params(), _frames(_trigger()))
    forced = m2.force_enter(10, "short")
    assert forced.action == "enter" and forced.side == "short" and "forced_anchor" in forced.reasons
    assert forced.invalidation_price == 60000.0 + 1500.0  # flat highs 60100 -> ATR level 61500 is wider
    assert m2.step(11).state == "in_position"
    m2.force_flat(12, "liquidation")
    assert m2.step(13).state == "flat"


def test_replay_is_causal_truncating_the_future_never_changes_the_past():
    t = _long_with_add(40)
    frames = _frames(t)
    whole = [d.to_dict() for d in _run(frames)]
    cut = [d.to_dict() for d in _run({**frames, "4h": t.iloc[:25]})]
    assert [w["action"] for w in whole[:25]] == [c["action"] for c in cut]
    assert [w["layers"] for w in whole[:25]] == [c["layers"] for c in cut]
