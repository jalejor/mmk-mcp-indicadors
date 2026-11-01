"""Round 8 regime identifiers (`impulse_regime`): every expected value is derived by hand
from the rule (last CLOSED 1d candle at the trigger close; close > EMA200 -> up), on tiny
synthetic frames. No market data."""

import numpy as np
import pandas as pd
import pytest

from controllers.metrics.impulse_backtest import TIMEFRAME_MS
from controllers.metrics.impulse_regime import (
    DOWN,
    UP,
    RegimeSeries,
    book_of,
    decision_ms,
    ema,
    label_signal,
    regime_series,
    side_matches,
)

DAY = TIMEFRAME_MS["1d"]
HOUR = TIMEFRAME_MS["1h"]
T0 = 1_700_000_000_000 - (1_700_000_000_000 % DAY)  # a midnight


def _daily(closes):
    ts = np.arange(len(closes), dtype="int64") * DAY + T0
    return pd.DataFrame({"timestamp": ts, "close": np.asarray(closes, dtype=float)})


def test_ema_is_the_adjusted_pandas_ewm():
    s = pd.Series([1.0, 2.0, 3.0])
    assert ema(s, span=2).tolist() == pytest.approx(s.ewm(span=2, adjust=True).mean().tolist())


def test_regime_is_close_vs_ema_per_closed_candle():
    # rising then falling prices: the last candle closes below the EMA of the series.
    closes = [10, 11, 12, 13, 14, 15, 5]
    rs = regime_series(_daily(closes))
    assert rs.n == 7 and rs.close_ms[0] == T0 + DAY  # close time = open + 1d
    assert rs.regime[-1] == -1 and rs.regime[1] == 1
    assert rs.at(T0 + 2 * DAY)["regime"] == UP


def test_at_uses_the_last_candle_closed_at_or_before_the_decision():
    rs = regime_series(_daily([10, 11, 12, 13, 14, 15, 5]))
    # before the first close: nothing
    assert rs.at(T0 + DAY - 1) is None
    # exactly at the first close: that candle counts (closed == decided at the same instant)
    assert rs.at(T0 + DAY)["candle_close"] == T0 + DAY
    # one hour into day 7 (last candle, close below EMA): the regime is still day 6's
    assert rs.at(T0 + 6 * DAY + HOUR)["regime"] == UP
    assert rs.at(T0 + 7 * DAY)["regime"] == DOWN


def test_decision_time_is_the_trigger_candle_close():
    assert decision_ms(T0, "1h") == T0 + HOUR and decision_ms(T0, "4h") == T0 + 4 * HOUR


def test_label_signal_reports_both_identifiers_and_tolerates_missing_series():
    own = regime_series(_daily([10, 11, 12]))
    btc = regime_series(_daily([12, 11, 5]))
    lab = label_signal(T0 + 2 * DAY + 5 * HOUR, "1h", own, btc)
    assert lab["regime_own"] == UP and lab["regime_btc"] == DOWN
    none = label_signal(T0 + 2 * DAY, "1h", None, btc)
    assert none["regime_own"] is None and none["regime_own_detail"] is None


def test_books_membership():
    assert side_matches("long", UP) is True and side_matches("long", DOWN) is False
    assert side_matches("short", DOWN) is True and side_matches("short", None) is None
    b = book_of("short", {"regime_own": DOWN, "regime_btc": UP})
    assert b == {"long_only": False, "short_only": True, "regime_own": True, "regime_btc": False, "regime": True}
    assert book_of("long", {"regime_own": None, "regime_btc": None})["regime"] is False


def test_share_up_over_a_window():
    rs = RegimeSeries(close_ms=np.array([1, 2, 3, 4]), regime=np.array([1, -1, 1, 1]),
                      ema=np.zeros(4), close=np.zeros(4))
    assert rs.share_up() == 0.75 and rs.share_up(start_ms=2, end_ms=3) == 0.5 and rs.share_up(start_ms=9) is None
