"""R-FEP-CONT study engine — pre-registered in `docs/PREREG_FEP_CONT_v0.3.0.md`.

A NEW module on purpose (same reasoning as `setup_backtest_service`): it
touches **no** live rule path. `rule_v020.py`, `monitors_v020.py`,
`rules_service.py` and `setup_service.py` are read-only for this study —
the false-entry state machine is consumed exactly as shipped.

What it does
------------
Replays four arms over history, all resolved by the SAME committed outcome
resolver (`SetupBacktestService._simulate_outcome`), with the same ATR trade
model, the same fee/slippage model and the same enrichment used by the F0
run that produced the PB-1D liston:

* ``FEP-CONT``  — rising edge of ``FALSE_ENTRY_PROBABLE``, side = cross
  direction. **The hypothesis**: a false entry is a slow real entry.
* ``CONFIRMED`` — rising edge of ``CONFIRMED`` (doctrine arm).
* ``BASE-RATE`` — unconditional entry every N-th bar, both sides. **The
  control group** the 2026-08-16 re-council made a blocking condition.
* ``WHIPSAW``   — rising edge of ``WHIPSAW`` (negative control).

Nothing here decides anything: it emits signals with a net-R outcome and a
stamped ``outcome_vara``. The gate lives in the pre-registration.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

from .market_data_service import MarketDataService
from .setup_backtest_service import (
    DEFAULT_FEE_RATE_PER_SIDE,
    DEFAULT_SLIPPAGE_PER_SIDE,
    CandidateSignal,
    SetupBacktestService,
)
from .setup_service import (
    FALSE_ENTRY_DEFAULTS,
    FE_CONFIRMED,
    FE_FALSE_ENTRY_PROBABLE,
    FE_WHIPSAW,
    TIMEFRAME_SECONDS,
    false_entry_state,
)
from .sizing_profiles import atr_sizing_for

# Pre-registration §2/§3/§4 — frozen 2026-08-22, commit 0154a40.
ARM_FEP_CONT = "FEP-CONT"
ARM_CONFIRMED = "CONFIRMED"
ARM_BASE_RATE = "BASE-RATE"
ARM_WHIPSAW = "WHIPSAW"
ARMS = (ARM_FEP_CONT, ARM_CONFIRMED, ARM_BASE_RATE, ARM_WHIPSAW)

_ARM_BY_STATE = {
    FE_FALSE_ENTRY_PROBABLE: ARM_FEP_CONT,
    FE_CONFIRMED: ARM_CONFIRMED,
    FE_WHIPSAW: ARM_WHIPSAW,
}

# §2: warm-up and the trailing window used to call the state machine. The
# 300-bar window is asserted equivalent to the full-series call by
# tests/test_fep_cont_golden.py; if that ever breaks, the run is invalid.
WARMUP_BARS = 300
STATE_WINDOW_BARS = 300
BASE_RATE_STRIDE = 20

ENTRY_MODE_CLOSE = "close"
ENTRY_MODE_NEXT_OPEN = "next_open"

_UNSET = object()  # edge-detector sentinel: "no previous state observed yet"


def outcome_vara(
    *,
    atr_stop_multiplier: float,
    target_r_multiple: float,
    fee_rate_per_side: float,
    slippage_per_side: float,
    entry_mode: str,
    time_stop_bars: Optional[int],
) -> str:
    """The yardstick, stamped into every record (re-council blocker #2)."""
    time_stop = f"|time_stop={time_stop_bars}b" if time_stop_bars else ""
    return (
        f"atr14x{atr_stop_multiplier}_stop|{target_r_multiple}R_target|"
        f"stop_first_intrabar|fee{fee_rate_per_side}+slip{slippage_per_side}_per_side|"
        f"resolver=setup_backtest_service._simulate_outcome|entry={entry_mode}{time_stop}"
    )


@dataclass
class FepSignal:
    """One arm entry with its resolved, size-independent net R."""

    arm: str
    symbol: str
    timeframe: str
    side: str  # long | short
    direction: str  # up | down (cross direction; base-rate carries the side)
    entry_time: str
    entry_price: float
    atr: float
    stop_price: float
    target_price: float
    exit_time: Optional[str]
    exit_price: float
    exit_reason: str
    bars_held: int
    r_net: float
    block: str  # in_sample | out_of_sample
    event_age: Optional[int] = None
    adx_turn_grade: Optional[str] = None
    cluster: str = ""  # (symbol, YYYY-MM) — the bootstrap cluster


@dataclass(frozen=True)
class ArmEvent:
    """An arm entry before any trade model is applied (detection output)."""

    arm: str
    bar_index: int
    side: str
    direction: str
    event_age: Optional[int] = None
    adx_turn_grade: Optional[str] = None


@dataclass
class FrameManifest:
    """Data provenance for the result JSON (re-council blocker #5)."""

    symbol: str
    timeframe: str
    exchange: str
    rows: int
    first_open: str
    last_open: str
    sha256: str
    fetch_seconds: float


class FepContBacktest:
    """Runs the four arms for one (symbol, timeframe) cell."""

    def __init__(
        self,
        *,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
        is_boundary: datetime,
        exchange: str = "binance",
        risk_profile: str = "medium",
        fee_rate_per_side: float = DEFAULT_FEE_RATE_PER_SIDE,
        slippage_per_side: float = DEFAULT_SLIPPAGE_PER_SIDE,
        entry_mode: str = ENTRY_MODE_CLOSE,
        time_stop_bars: Optional[int] = None,
        base_rate_stride: int = BASE_RATE_STRIDE,
        state_window_bars: int = STATE_WINDOW_BARS,
        warmup_bars: int = WARMUP_BARS,
    ) -> None:
        if entry_mode not in (ENTRY_MODE_CLOSE, ENTRY_MODE_NEXT_OPEN):
            raise ValueError(f"unknown entry_mode {entry_mode!r}")
        self.symbol = symbol
        self.timeframe = timeframe
        self.start = _utc(start)
        self.end = _utc(end)
        self.is_boundary = _utc(is_boundary)
        self.exchange = exchange
        self.risk_profile = risk_profile
        self.fee_rate_per_side = float(fee_rate_per_side)
        self.slippage_per_side = float(slippage_per_side)
        self.entry_mode = entry_mode
        self.time_stop_bars = time_stop_bars
        self.base_rate_stride = int(base_rate_stride)
        self.state_window_bars = int(state_window_bars)
        self.warmup_bars = int(warmup_bars)
        self.atr_stop_multiplier, self.target_r_multiple = atr_sizing_for(risk_profile)

        # The committed resolver, reused verbatim. `setups=[]` keeps the
        # declarative engine out of the way — only `_simulate_outcome` is used.
        self._resolver_host = SetupBacktestService(
            symbol=symbol,
            start=self.start,
            end=self.end,
            exchange=exchange,
            setups=[],
            risk_profile=risk_profile,  # type: ignore[arg-type]
            fee_rate_per_side=self.fee_rate_per_side,
            slippage_per_side=self.slippage_per_side,
        )
        self.manifest: Optional[FrameManifest] = None

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------
    def _warmup_delta(self) -> timedelta:
        """How far before `start` the frame must begin for indicator warm-up."""
        return timedelta(seconds=TIMEFRAME_SECONDS[self.timeframe] * self.warmup_bars)

    def load_frame(self, raw: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """Fetch (or accept) raw OHLCV, stamp the manifest, enrich once."""
        t0 = time.time()
        if raw is None:
            raw = self.fetch_ohlcv(
                symbol=self.symbol,
                timeframe=self.timeframe,
                start=self.start - self._warmup_delta(),
                end=self.end,
                exchange=self.exchange,
            )
        fetch_s = time.time() - t0
        if raw.empty:
            raise ValueError(f"no OHLCV for {self.symbol} {self.timeframe}")
        self.manifest = FrameManifest(
            symbol=self.symbol,
            timeframe=self.timeframe,
            exchange=self.exchange,
            rows=len(raw),
            first_open=raw.index[0].isoformat(),
            last_open=raw.index[-1].isoformat(),
            sha256=ohlcv_sha256(raw),
            fetch_seconds=round(fetch_s, 2),
        )
        # Same enrichment code path as the F0 run behind the liston.
        return SetupBacktestService.enrich(raw)

    @staticmethod
    def fetch_ohlcv(
        *, symbol: str, timeframe: str, start: datetime, end: datetime, exchange: str
    ) -> pd.DataFrame:
        """Forward-paginated OHLCV, closed candles only.

        `limit`: binance honours `since` with 1000 rows/page; bitget silently
        caps/gaps old ranges above 200 (known error E13), so it drops to 200.
        """
        ex = MarketDataService(exchange_name=exchange).exchange
        duration_ms = TIMEFRAME_SECONDS[timeframe] * 1000
        limit = 1000 if exchange == "binance" else 200
        since_ms = int(_utc(start).timestamp() * 1000)
        end_ms = int(_utc(end).timestamp() * 1000)
        rows: List[List[Any]] = []
        cursor = since_ms
        while cursor < end_ms:
            batch = ex.fetch_ohlcv(symbol=symbol, timeframe=timeframe, since=cursor, limit=limit)
            if not batch:
                break
            rows.extend(batch)
            nxt = batch[-1][0] + duration_ms
            if nxt <= cursor:
                break
            cursor = nxt
            if len(batch) < limit:
                break
        if not rows:
            raise ValueError(f"No OHLCV data returned for {symbol} {timeframe}")
        df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df = df.drop_duplicates(subset="timestamp").sort_values("timestamp").set_index("datetime")
        df = df[df.index <= pd.Timestamp(_utc(end))]
        now_ms = time.time() * 1000.0
        if len(df) and int(df["timestamp"].iloc[-1]) + duration_ms > now_ms:
            df = df.iloc[:-1]  # spec §0.1: closed candles only
        return df

    # ------------------------------------------------------------------
    # Arms — detection is separated from resolution on purpose: the state
    # machine is the expensive half and is identical across sensitivities
    # (which only change the trade model), so it runs ONCE per cell.
    # ------------------------------------------------------------------
    def collect(self, df: pd.DataFrame, events: Optional[List["ArmEvent"]] = None) -> List[FepSignal]:
        """All four arms over one enriched frame, chronologically."""
        if events is None:
            events = self.detect_events(df)
        signals = [s for s in (self.resolve_event(df, ev) for ev in events) if s is not None]
        signals.sort(key=lambda s: s.entry_time)
        return signals

    def detect_events(self, df: pd.DataFrame) -> List["ArmEvent"]:
        """Every arm entry (bar index + side), before any trade model."""
        events = self._detect_state_events(df)
        events.extend(self._detect_base_rate_events(df))
        events.sort(key=lambda e: (e.bar_index, e.arm, e.side))
        return events

    def _detect_state_events(self, df: pd.DataFrame) -> List["ArmEvent"]:
        n = len(df)
        ao = df["ao"]
        adx, pdi, mdi = df["adx14"], df["plus_di"], df["minus_di"]
        out: List[ArmEvent] = []
        # `_UNSET` primes the edge detector: the state carried by the first
        # evaluated bar is inherited, never emitted as a fresh transition.
        previous: Dict[str, Any] = {"up": _UNSET, "down": _UNSET}
        start_ts = pd.Timestamp(self.start)
        win = self.state_window_bars

        for i in range(self.warmup_bars, n - 1):  # never open on the last bar
            lo = max(0, i - win + 1) if win else 0
            sl = slice(lo, i + 1)
            bar_time = df.index[i]
            for direction in ("up", "down"):
                fe = false_entry_state(
                    ao.iloc[sl],
                    adx.iloc[sl],
                    pdi.iloc[sl],
                    mdi.iloc[sl],
                    direction=direction,
                    params=FALSE_ENTRY_DEFAULTS,
                )
                state = fe.state
                rising_edge = (
                    state is not None
                    and previous[direction] is not _UNSET
                    and state != previous[direction]
                )
                previous[direction] = state
                if not rising_edge:
                    continue
                arm = _ARM_BY_STATE.get(state or "")
                if arm is None:  # WATCHING is not an arm
                    continue
                if bar_time < start_ts:
                    continue
                out.append(
                    ArmEvent(
                        arm=arm,
                        bar_index=i,
                        side="long" if direction == "up" else "short",
                        direction=direction,
                        event_age=fe.event_age,
                        adx_turn_grade=(fe.adx_turn or {}).get("grade") if fe.adx_turn else None,
                    )
                )
        return out

    def _detect_base_rate_events(self, df: pd.DataFrame) -> List["ArmEvent"]:
        """Unconditional control: every stride-th bar, both sides."""
        out: List[ArmEvent] = []
        start_ts = pd.Timestamp(self.start)
        for i in range(self.warmup_bars, len(df) - 1, self.base_rate_stride):
            if df.index[i] < start_ts:
                continue
            for side, direction in (("long", "up"), ("short", "down")):
                out.append(
                    ArmEvent(arm=ARM_BASE_RATE, bar_index=i, side=side, direction=direction)
                )
        return out

    def resolve_event(self, df: pd.DataFrame, event: "ArmEvent") -> Optional[FepSignal]:
        return self._make_signal(
            df,
            event.bar_index,
            arm=event.arm,
            side=event.side,
            direction=event.direction,
            event_age=event.event_age,
            adx_turn_grade=event.adx_turn_grade,
        )

    # ------------------------------------------------------------------
    # Outcome (the committed resolver, called verbatim)
    # ------------------------------------------------------------------
    def _make_signal(
        self,
        df: pd.DataFrame,
        i: int,
        *,
        arm: str,
        side: str,
        direction: str,
        event_age: Optional[int],
        adx_turn_grade: Optional[str],
    ) -> Optional[FepSignal]:
        atr = float(df["atr14"].iloc[i]) if "atr14" in df else 0.0
        if not (atr > 0):
            return None
        if self.entry_mode == ENTRY_MODE_CLOSE:
            entry_price = float(df["close"].iloc[i])
        else:  # next_open — walk still starts at i+1, so that bar can stop us
            entry_price = float(df["open"].iloc[i + 1])
        if not (entry_price > 0):
            return None

        candidate = CandidateSignal(
            setup_id=arm,
            side=side,
            bar_index=i,
            entry_time=df.index[i].to_pydatetime(),
            entry_price=entry_price,
            atr=atr,
        )
        forward = df
        if self.time_stop_bars:
            forward = df.iloc[: i + 1 + int(self.time_stop_bars)]
        self._resolver_host._simulate_outcome(candidate, forward)

        reason = candidate.exit_reason
        if self.time_stop_bars and reason == "end_of_data" and len(forward) < len(df):
            reason = "time_stop"

        entry_dt = candidate.entry_time
        return FepSignal(
            arm=arm,
            symbol=self.symbol,
            timeframe=self.timeframe,
            side=side,
            direction=direction,
            entry_time=entry_dt.isoformat(),
            entry_price=round(entry_price, 8),
            atr=round(atr, 8),
            stop_price=round(candidate.stop_price, 8),
            target_price=round(candidate.target_price, 8),
            exit_time=candidate.exit_time.isoformat() if candidate.exit_time else None,
            exit_price=round(candidate.exit_price, 8),
            exit_reason=reason,
            bars_held=candidate.bars_held,
            r_net=round(candidate.r_net, 6),
            block="in_sample" if entry_dt < self.is_boundary else "out_of_sample",
            event_age=event_age,
            adx_turn_grade=adx_turn_grade,
            cluster=f"{self.symbol}|{entry_dt:%Y-%m}",
        )

    # ------------------------------------------------------------------
    def vara(self) -> str:
        return outcome_vara(
            atr_stop_multiplier=self.atr_stop_multiplier,
            target_r_multiple=self.target_r_multiple,
            fee_rate_per_side=self.fee_rate_per_side,
            slippage_per_side=self.slippage_per_side,
            entry_mode=self.entry_mode,
            time_stop_bars=self.time_stop_bars,
        )


# ----------------------------------------------------------------------
# Portfolio basis (§6): max 1 concurrent position per symbol
# ----------------------------------------------------------------------

def portfolio_subset(signals: Sequence[FepSignal]) -> List[FepSignal]:
    """Greedy, chronological, non-overlapping subset — the economic reading.

    Mirrors `SetupBacktestService._execute_portfolio` (skip anything that
    starts before the open position closes), per symbol.
    """
    by_symbol: Dict[str, List[FepSignal]] = {}
    for sig in signals:
        by_symbol.setdefault(sig.symbol, []).append(sig)
    kept: List[FepSignal] = []
    for symbol, group in by_symbol.items():
        busy_until: Optional[str] = None
        for sig in sorted(group, key=lambda s: s.entry_time):
            if busy_until is not None and sig.entry_time < busy_until:
                continue
            kept.append(sig)
            busy_until = sig.exit_time or sig.entry_time
    kept.sort(key=lambda s: s.entry_time)
    return kept


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def ohlcv_sha256(df: pd.DataFrame) -> str:
    """Stable digest of the raw OHLCV matrix (provenance, not prices)."""
    cols = ["timestamp", "open", "high", "low", "close", "volume"]
    payload = df[cols].to_csv(index=False, float_format="%.8f").encode()
    return hashlib.sha256(payload).hexdigest()


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def signal_dicts(signals: Sequence[FepSignal]) -> List[Dict[str, Any]]:
    return [asdict(s) for s in signals]


# ----------------------------------------------------------------------
# Statistics (§6 of the pre-registration — method frozen before the run)
# ----------------------------------------------------------------------

BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 20260822


def metrics_block(signals: Sequence[FepSignal]) -> Dict[str, Any]:
    """Per-signal net-R metrics. Same definitions as the F0 gate report."""
    n = len(signals)
    if n == 0:
        return {"n": 0}
    rs = [s.r_net for s in signals]
    wins = [r for r in rs if r > 0]
    losses = [r for r in rs if r <= 0]
    gross_w = sum(wins)
    gross_l = abs(sum(losses))
    reasons: Dict[str, int] = {}
    for s in signals:
        reasons[s.exit_reason] = reasons.get(s.exit_reason, 0) + 1
    ordered = sorted(rs)
    return {
        "n": n,
        "expectancy_R": round(sum(rs) / n, 4),
        "median_R": round(ordered[n // 2], 4),
        "win_rate": round(len(wins) / n, 4),
        "avg_win_R": round(gross_w / len(wins), 3) if wins else 0.0,
        "avg_loss_R": round(sum(losses) / len(losses), 3) if losses else 0.0,
        "profit_factor": round(gross_w / gross_l, 3) if gross_l > 0 else (float("inf") if gross_w > 0 else 0.0),
        "total_R": round(sum(rs), 3),
        "avg_bars_held": round(sum(s.bars_held for s in signals) / n, 2),
        "exit_reasons": reasons,
        "unresolved": reasons.get("end_of_data", 0),
    }


def portfolio_block(signals: Sequence[FepSignal], *, years: float) -> Dict[str, Any]:
    """Economic reading: non-overlapping subset, total R, R/yr, trade-level DD."""
    kept = portfolio_subset(signals)
    block = metrics_block(kept)
    if not kept:
        return {**block, "R_per_year": 0.0, "max_drawdown_R": 0.0}
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for sig in kept:
        equity += sig.r_net
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    block["R_per_year"] = round(block["total_R"] / years, 3) if years > 0 else 0.0
    block["max_drawdown_R"] = round(max_dd, 3)
    return block


def _cluster_index(signals: Sequence[FepSignal]) -> Dict[str, List[int]]:
    idx: Dict[str, List[int]] = {}
    for i, s in enumerate(signals):
        idx.setdefault(s.cluster, []).append(i)
    return idx


def cluster_bootstrap_ci(
    signals: Sequence[FepSignal],
    *,
    resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
    alpha: float = 0.05,
) -> Dict[str, Any]:
    """95% percentile CI of the mean net R, resampling (symbol, month) clusters.

    FEP signals overlap; an i.i.d. bootstrap would understate the error. The
    naive CI is reported too, but never decides (pre-registration §6).
    """
    import numpy as np

    if not signals:
        return {"n": 0}
    rs = np.array([s.r_net for s in signals], dtype=float)
    clusters = _cluster_index(signals)
    keys = sorted(clusters)
    arrays = [rs[clusters[k]] for k in keys]
    sums = np.array([a.sum() for a in arrays])
    counts = np.array([len(a) for a in arrays])

    rng = np.random.default_rng(seed)
    k = len(keys)
    picks = rng.integers(0, k, size=(resamples, k))
    boot = sums[picks].sum(axis=1) / np.maximum(counts[picks].sum(axis=1), 1)
    lo, hi = np.percentile(boot, [100 * alpha / 2, 100 * (1 - alpha / 2)])

    # Naive i.i.d. CI: normal approximation (a resampling matrix over 10^5
    # signals would cost gigabytes for a number that never decides anything).
    se = float(rs.std(ddof=1) / np.sqrt(len(rs))) if len(rs) > 1 else 0.0
    n_lo, n_hi = float(rs.mean() - 1.96 * se), float(rs.mean() + 1.96 * se)
    return {
        "n": len(signals),
        "clusters": k,
        "mean_R": round(float(rs.mean()), 4),
        "ci95_cluster": [round(float(lo), 4), round(float(hi), 4)],
        "ci95_naive": [round(float(n_lo), 4), round(float(n_hi), 4)],
        "p_gt_zero_cluster": round(float((boot <= 0).mean()), 5),
    }


def cluster_bootstrap_difference(
    treatment: Sequence[FepSignal],
    control: Sequence[FepSignal],
    *,
    resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
    alpha: float = 0.05,
) -> Dict[str, Any]:
    """CI of `mean(treatment) - mean(control)`, clusters resampled JOINTLY."""
    import numpy as np

    if not treatment or not control:
        return {"n_treatment": len(treatment), "n_control": len(control)}
    t_idx = _cluster_index(treatment)
    c_idx = _cluster_index(control)
    keys = sorted(set(t_idx) | set(c_idx))
    t_r = np.array([s.r_net for s in treatment], dtype=float)
    c_r = np.array([s.r_net for s in control], dtype=float)
    t_sum = np.array([t_r[t_idx[k]].sum() if k in t_idx else 0.0 for k in keys])
    t_cnt = np.array([len(t_idx.get(k, []))for k in keys])
    c_sum = np.array([c_r[c_idx[k]].sum() if k in c_idx else 0.0 for k in keys])
    c_cnt = np.array([len(c_idx.get(k, [])) for k in keys])

    rng = np.random.default_rng(seed)
    k = len(keys)
    picks = rng.integers(0, k, size=(resamples, k))
    tm = t_sum[picks].sum(axis=1) / np.maximum(t_cnt[picks].sum(axis=1), 1)
    cm = c_sum[picks].sum(axis=1) / np.maximum(c_cnt[picks].sum(axis=1), 1)
    diff = tm - cm
    lo, hi = np.percentile(diff, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    point = float(t_r.mean() - c_r.mean())
    return {
        "n_treatment": len(treatment),
        "n_control": len(control),
        "clusters": k,
        "difference_R": round(point, 4),
        "ci95_cluster": [round(float(lo), 4), round(float(hi), 4)],
        "p_le_zero_cluster": round(float((diff <= 0).mean()), 5),
    }


def welch_p_one_sided(treatment: Sequence[float], control: Sequence[float]) -> Optional[float]:
    """One-sided Welch p-value for mean(treatment) > mean(control). Courtesy only."""
    import math

    import numpy as np

    if len(treatment) < 2 or len(control) < 2:
        return None
    a, b = np.array(treatment, dtype=float), np.array(control, dtype=float)
    va, vb = a.var(ddof=1) / len(a), b.var(ddof=1) / len(b)
    if va + vb <= 0:
        return None
    t = (a.mean() - b.mean()) / math.sqrt(va + vb)
    df = (va + vb) ** 2 / (va**2 / (len(a) - 1) + vb**2 / (len(b) - 1))
    # Normal approximation of the t tail (df is large in every cell here).
    return round(float(0.5 * math.erfc(t / math.sqrt(2))), 6) if df > 30 else None


def holm_adjust(pvalues: Dict[str, Optional[float]]) -> Dict[str, Optional[float]]:
    """Holm step-down correction across the reported cells (§6)."""
    items = [(k, v) for k, v in pvalues.items() if v is not None]
    items.sort(key=lambda kv: kv[1])
    m = len(items)
    out: Dict[str, Optional[float]] = {k: None for k in pvalues}
    running = 0.0
    for rank, (key, p) in enumerate(items):
        adj = min(1.0, (m - rank) * p)
        running = max(running, adj)
        out[key] = round(running, 6)
    return out
