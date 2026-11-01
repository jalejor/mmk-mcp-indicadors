"""Lead-time measurement (impulsos-v2 round 2) — synthetic candles, no network."""

import numpy as np
import pandas as pd
import pytest

from controllers.metrics.impulse_lead_time import (
    EVENT_SPECS,
    LeadTimeParams,
    detect_events,
    follower_window,
    measure,
    movement_starts,
    nearest_start,
)


def _frame(n: int, **cols) -> pd.DataFrame:
    base = {
        "close": np.full(n, 100.0), "atr14": np.full(n, 1.0), "bbwp": np.full(n, 40.0),
        "konkorde_verde": np.full(n, 10.0), "konkorde_media": np.full(n, 5.0),
        "adx14": np.full(n, 20.0), "plus_di": np.full(n, 20.0), "minus_di": np.full(n, 15.0),
        "ao": np.full(n, 1.0), "macd": np.full(n, 1.0), "macd_signal": np.full(n, 0.5),
        "rsi14": np.full(n, 55.0),
    }
    base.update(cols)
    return pd.DataFrame(base, index=pd.date_range("2025-01-01", periods=n, freq="4h", tz="UTC"))


def _bars(mask: np.ndarray) -> list:
    return [int(i) for i in np.flatnonzero(mask)]


def test_every_spec_has_a_detector():
    events = detect_events(_frame(30))
    assert set(events) == {s.name for s in EVENT_SPECS}
    assert all(not m.any() for m in events.values())  # flat frame: nothing fires


def test_konkorde_events():
    verde = np.full(20, 10.0)
    verde[5], verde[6] = -1.0, 2.0  # down at 5, up at 6 (zero line)
    media = np.full(20, 5.0)
    verde[12] = 3.0  # below media at 12, back above at 13
    ev = detect_events(_frame(20, konkorde_verde=verde, konkorde_media=media))
    assert _bars(ev["konkorde_zero_cross_down"]) == [5]
    assert _bars(ev["konkorde_zero_cross_up"]) == [6]
    assert _bars(ev["konkorde_turn_down"]) == [5, 12]
    assert _bars(ev["konkorde_turn_up"]) == [7, 13]  # 6: verde 2 < media 5


def test_bbwp_events():
    bbwp = np.full(30, 40.0)
    bbwp[8:12] = [25.0, 35.0, 45.0, 55.0]  # compression at 8, crosses 50 at 11
    bbwp[25:28] = [95.0, 90.0, 80.0]  # drops: 5 (no), 10 from 90 (yes, at 27)
    ev = detect_events(_frame(30, bbwp=bbwp))
    assert _bars(ev["bbwp_ignition"]) == [11]
    assert _bars(ev["bbwp_red_turn"]) == [27]

    stale = np.full(30, 40.0)
    stale[3] = 25.0
    stale[20] = 55.0  # compression 17 bars earlier: outside the 10-bar lookback
    assert not detect_events(_frame(30, bbwp=stale))["bbwp_ignition"].any()


def test_follower_events():
    n = 30
    ao = np.array([3.0, 2.0, 1.0, 0.5, -0.5, -1.0, -0.8, -0.2, 0.4] + [0.4] * (n - 9))
    rsi = np.full(n, 55.0)
    rsi[10:14] = [45.0, 52.0, 25.0, 31.0]
    rsi[20:22] = [75.0, 69.0]
    macd = np.full(n, 1.0)
    macd[15] = 0.0
    ev = detect_events(_frame(n, ao=ao, rsi14=rsi, macd=macd))
    assert _bars(ev["ao_zero_cross_down"]) == [4]
    assert _bars(ev["ao_zero_cross_up"]) == [8]
    assert 6 in _bars(ev["ao_turn_up"])  # slope -0.5 -> +0.2
    assert _bars(ev["rsi_cross_50_down"]) == [10, 12]
    assert _bars(ev["rsi_cross_50_up"]) == [11, 14]
    assert _bars(ev["rsi_exit_oversold"]) == [13]
    assert _bars(ev["rsi_exit_overbought"]) == [21]
    assert _bars(ev["macd_cross_down"]) == [15]
    assert _bars(ev["macd_cross_up"]) == [16]


def test_adx_turn_up_onset_takes_the_dominant_di_side():
    n = 30
    adx = np.full(n, 15.0)
    adx[10:] = 15.0 + 3.0 * np.arange(1, n - 9)  # sharp turn from flat
    ev = detect_events(_frame(n, adx14=adx))
    # bar 10: slope 1.0 but delta 1.0 < 1.5; bar 11: slope 2, delta 2 -> state on 11..14
    assert _bars(ev["adx_turn_up_long"]) == [11]  # onset only, +DI dominant
    assert not ev["adx_turn_up_short"].any()
    ev_s = detect_events(_frame(n, adx14=adx, plus_di=np.full(n, 10.0)))
    assert _bars(ev_s["adx_turn_up_short"]) == [11]


def test_movement_starts_and_dedupe():
    close = np.full(40, 100.0)
    close[6:12] = [101.0, 102.0, 103.0, 103.0, 103.0, 103.0]  # +3 ATR within 10 bars of 3..5
    close[12:] = 103.0
    close[30:35] = [100.0, 99.0, 98.0, 97.0, 97.0]
    close[35:] = 97.0
    starts = movement_starts(_frame(40, close=close), LeadTimeParams(horizon=10, k_atr=2.0))
    # earliest bar whose next 10 closes reach +2 is 0 (close[7] = 102); dedupe drops 1..10
    assert list(starts[1]) == [0]
    assert list(starts[-1]) == [20]  # 103 -> 100 at bar 30; needs a full horizon (m < 30)


def test_nearest_start_window_and_ties():
    p = LeadTimeParams(max_lead=12, min_lead=-2)
    starts = np.array([8, 12, 40])
    assert nearest_start(10, starts, p) == 12  # |+2| ties |-2| -> prefer forward
    assert nearest_start(20, starts, p) is None  # 12 is -8, 40 is +20
    assert nearest_start(27, starts, p) is None  # 40 is +13 > L
    assert nearest_start(28, starts, p) == 40
    assert nearest_start(41, starts, p) == 40  # -1 >= min_lead
    assert nearest_start(43, starts, p) is None


def test_measure_lead_and_lag_on_a_planted_move():
    n = 80
    close = np.full(n, 104.0)
    close[40] = 100.0
    close[41:] = 105.0  # long move starts exactly at 40 (earlier bars see only +1)
    verde = np.full(n, -5.0)
    verde[35:] = 5.0  # leader zero cross up at 35 (lead 5)
    ao = np.full(n, -1.0)
    ao[38:] = 1.0  # follower AO cross up at 38 (lag 3)
    macd = np.full(n, 0.0)
    macd[39:] = 1.0  # MACD cross up at 39 (lag 4)
    df = _frame(n, close=close, konkorde_verde=verde, konkorde_media=np.full(n, 100.0),
                ao=ao, macd=macd, macd_signal=np.full(n, 0.5))
    res = measure(df, np.ones(n, dtype=bool), LeadTimeParams())
    k = res["events"]["konkorde_zero_cross_up"]
    assert (k["n"], k["hits"], k["lead"]["median"]) == (1, 1, 5.0)
    assert res["events"]["ao_zero_cross_up"]["lead"]["median"] == 2.0
    lag = res["lag_follower_minus_leader"]["konkorde_zero_cross_up"]
    assert lag["followers"]["ao_zero_cross_up"]["median"] == 3.0
    assert lag["followers"]["macd_cross_up"]["median"] == 4.0
    assert lag["pooled"]["n_pairs"] == 2
    assert res["move_starts"] == {"long": 1, "short": 1}  # the 104 -> 100 dip starts at 30
    # Events outside the block are not counted.
    outside = measure(df, np.arange(n) < 30, LeadTimeParams())
    assert outside["events"]["konkorde_zero_cross_up"]["n"] == 0


@pytest.mark.parametrize("p75,expected", [(None, None), (0.5, 2), (3.2, 4), (20.0, 8)])
def test_follower_window_clamp(p75, expected):
    assert follower_window(p75, 2, 8) == expected
