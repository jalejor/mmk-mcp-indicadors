"""Round 6 (docs/PREREG_IMPULSOS_v2_r6.md): ablation knob `ctx_mlrsi_entry_block`.

Owner point (f) 2026-11-01: the guardian ML RSI exit is new and closes 71 % of the 4h
trades; it must be measured with and without. `ctx_mlrsi_exit` controlled BOTH the exit
(#3 of the 2.2.0 chain) and the entry block (`ctx_mlrsi_against` at ENTER). The knob
decouples them: None (default) = 2.2.0 behaviour byte-identical; False/True override the
entry block alone. Every expected outcome is derived from the rule, on the round-4b
fixtures (S02 long: leader at 10, AO 11, MACD 12 -> ENTER at 12; guardian red from the
daily candle of 2026-01-12 -> trigger bar 17).
"""

import pandas as pd

from controllers.metrics.impulse_sequential import R4_OVERRIDES, R5_OVERRIDES, SequentialMachine, r5_params
from test_impulse_r4 import _r4_frames
from test_impulse_sequential import GOLDEN_WINDOWS, N, _long_setup


def _p(**overrides):
    return r5_params("pro", confirm_window_bars=dict(GOLDEN_WINDOWS), **overrides)


def _run(frames, params):
    return SequentialMachine(params, frames).run()


def _red_guardian_from_jan12(frames):
    g = frames["1d"]
    regime = pd.Series("gray", index=g.index)
    regime[g.index >= pd.Timestamp("2026-01-12", tz="UTC")] = "red"
    g["ml_rsi_regime"] = regime
    return frames


def test_default_knob_follows_ctx_mlrsi_exit_and_is_not_in_the_frozen_overrides():
    p = _p()
    assert p.ctx_mlrsi_entry_block is None and p.ctx_mlrsi_exit is True and p.ctx_mlrsi_blocks_entry is True
    assert "ctx_mlrsi_entry_block" not in R4_OVERRIDES and "ctx_mlrsi_entry_block" not in R5_OVERRIDES
    off = _p(ctx_mlrsi_exit=False)
    assert off.ctx_mlrsi_blocks_entry is False
    assert _p(ctx_mlrsi_exit=False, ctx_mlrsi_entry_block=True).ctx_mlrsi_blocks_entry is True
    assert _p(ctx_mlrsi_exit=True, ctx_mlrsi_entry_block=False).ctx_mlrsi_blocks_entry is False


def test_exit_off_with_entry_block_kept_holds_through_the_red_guardian():
    """Pure exit ablation: same ENTER at 12, no `exit_ctx_mlrsi_against` at 17, trade still open at the end."""
    frames = _red_guardian_from_jan12(_r4_frames(_long_setup(N)))
    on = _run(frames, _p())
    assert on[12].action == "enter" and on[17].action == "exit" and "exit_ctx_mlrsi_against" in on[17].reasons
    off = _run(frames, _p(ctx_mlrsi_exit=False, ctx_mlrsi_entry_block=True))
    assert off[12].action == "enter"
    assert all("exit_ctx_mlrsi_against" not in d.reasons for d in off)
    assert off[N - 1].state == "in_position"
    # the guardian regime is still computed and reported while the position is open
    assert off[17].context.get("ctx_mlrsi_regime") == "red"


def test_entry_block_kept_still_blocks_a_red_guardian_at_enter_when_the_exit_is_off():
    frames = _r4_frames(_long_setup(N))
    frames["1d"]["ml_rsi_regime"] = "red"
    blocked = _run(frames, _p(ctx_mlrsi_exit=False, ctx_mlrsi_entry_block=True))[12]
    assert blocked.action == "alert" and "ctx_mlrsi_against" in blocked.reasons
    # both off: the red guardian neither blocks nor exits
    both_off = _run(frames, _p(ctx_mlrsi_exit=False))
    assert both_off[12].action == "enter" and both_off[N - 1].state == "in_position"
    assert all("ctx_mlrsi_against" not in d.reasons and "exit_ctx_mlrsi_against" not in d.reasons for d in both_off)


def test_knob_none_reproduces_the_2_2_0_decisions_exactly():
    frames = _red_guardian_from_jan12(_r4_frames(_long_setup(N)))
    a = _run(frames, _p())
    b = _run(frames, _p(ctx_mlrsi_entry_block=True))
    assert [(d.action, d.state, tuple(d.reasons)) for d in a] == [(d.action, d.state, tuple(d.reasons)) for d in b]
