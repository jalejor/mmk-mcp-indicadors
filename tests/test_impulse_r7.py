"""Round 7 (docs/PREREG_IMPULSOS_v2_r7.md): multi-asset statistics of `impulse_multi`.

Every expected value is derived by hand from the definitions in the prereg (Holm
step-down, BH step-up, cluster bootstrap p, pooled drawdown, leave-one-out), on tiny
synthetic trade lists — no market data, no machine run.
"""

from dataclasses import dataclass

import pytest

from controllers.metrics.impulse_multi import (
    benjamini_hochberg,
    holm,
    leave_one_out,
    p_positive,
    per_symbol_breakdown,
    pooled_drawdown,
    symbol_of,
    verdict_r7,
)


@dataclass
class T:
    r_net: float
    cluster: str
    block: str = "out_of_sample"
    pnl_net_usdt: float = 0.0
    entry_time: str = "2026-01-01T00:00:00+00:00"


def _t(r, sym="ETH/USDT", month="2026-01", block="out_of_sample", pnl=None, when=None):
    return T(r_net=r, cluster=f"{sym}|{month}", block=block, pnl_net_usdt=r * 10.0 if pnl is None else pnl,
             entry_time=when or f"{month}-15T00:00:00+00:00")


def test_symbol_of_reads_the_cluster_prefix():
    assert symbol_of(_t(1.0, "DOGE/USDT")) == "DOGE/USDT"


def test_holm_step_down_by_hand():
    # m = 4, sorted p: 0.001, 0.02, 0.03, None(=1). adjusted: 4*0.001=0.004; 3*0.02=0.06; 2*0.03=0.06 (monotone); None stays None.
    out = holm({"a": 0.02, "b": 0.001, "c": 0.03, "d": None}, alpha=0.05)
    assert out["b"]["p_adj"] == pytest.approx(0.004) and out["b"]["reject"] is True
    assert out["a"]["p_adj"] == pytest.approx(0.06) and out["a"]["reject"] is False
    assert out["c"]["p_adj"] == pytest.approx(0.06) and out["c"]["reject"] is False
    assert out["d"]["p_adj"] is None and out["d"]["reject"] is False and out["d"]["m"] == 4


def test_bh_step_up_by_hand():
    # m = 4, sorted p: 0.01, 0.02, 0.03, 0.5 -> raw m*p/i: 0.04, 0.04, 0.04, 0.5 -> step-up min from the right: 0.04, 0.04, 0.04, 0.5
    out = benjamini_hochberg({"a": 0.03, "b": 0.01, "c": 0.02, "d": 0.5}, q=0.10)
    assert out["b"]["q_value"] == pytest.approx(0.04) and out["a"]["q_value"] == pytest.approx(0.04)
    assert out["d"]["q_value"] == pytest.approx(0.5)
    assert [out[k]["reject"] for k in "abcd"] == [True, True, True, False]


def test_p_positive_is_one_sided_and_floored():
    good = [_t(1.0, month=f"2026-0{m}") for m in range(1, 7)]  # every cluster positive -> no resample <= 0
    assert p_positive(good, resamples=1000) == pytest.approx(1 / 1000)
    bad = [_t(-1.0, month=f"2026-0{m}") for m in range(1, 7)]
    assert p_positive(bad, resamples=1000) == 1.0
    assert p_positive([_t(1.0), _t(2.0)]) is None  # one cluster: degenerate


def test_p_positive_resamples_clusters_not_trades():
    # Two clusters: one with 5 trades of +1, one with a single -10. Resampling clusters (k=2) gives
    # mean <= 0 whenever the bad cluster is drawn at least once with the good one (or twice): P = 3/4.
    trades = [_t(1.0, month="2026-01")] * 5 + [_t(-10.0, month="2026-02")]
    p = p_positive(trades, resamples=4000)
    assert 0.70 < p < 0.80


def test_pooled_drawdown_uses_the_pooled_start():
    trades = [_t(0, pnl=+50, when="2026-01-01"), _t(0, pnl=-120, when="2026-01-02"), _t(0, pnl=+30, when="2026-01-03")]
    dd = pooled_drawdown(trades, start_total=2 * 1300.0)
    assert dd["max_drawdown_usdt"] == 120.0 and dd["pnl_net_usdt"] == -40.0
    assert dd["max_drawdown_pct_initial"] == pytest.approx(120 / 2600 * 100, abs=0.01)


def test_breakdown_and_leave_one_out():
    trades = [_t(1.0, "ETH/USDT"), _t(1.0, "ETH/USDT", block="in_sample"), _t(-2.0, "ADA/USDT")]
    bd = per_symbol_breakdown(trades, "out_of_sample")
    assert bd["ETH/USDT"] == {"n": 2, "n_oos": 1, "sum_r": 2.0, "exp_r": 1.0, "exp_oos": 1.0, "pnl_net_usdt": 20.0}
    assert bd["ADA/USDT"]["sum_r"] == -2.0
    loo = leave_one_out(trades, "out_of_sample")
    assert loo["ADA/USDT"]["exp_without"] == 1.0 and loo["ADA/USDT"]["adds"] is False  # removing ADA raises the pool (0 -> 1)
    assert loo["ETH/USDT"]["exp_without"] == -2.0 and loo["ETH/USDT"]["adds"] is True


def test_verdict_r7_requires_both_legs():
    go = {"verdict": "GO", "failed": []}
    assert verdict_r7(go, {"method": "holm", "p_adj": 0.01, "m": 12, "reject": True}, label="primary")["verdict"] == "GO"
    v = verdict_r7(go, {"method": "holm", "p_adj": 0.3, "m": 12, "reject": False}, label="primary")
    assert v["verdict"] == "NO-GO" and "multiple comparisons" in v["failed"][0]
    assert verdict_r7(go, None, label="secondary")["verdict"] == "NO-GO"
    inc = {"verdict": "INCONCLUSIVE", "failed": ["n_total=7 < 30"]}
    assert verdict_r7(inc, {"reject": True, "method": "bh"}, label="asset")["verdict"] == "INCONCLUSIVE"
