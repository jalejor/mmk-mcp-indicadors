"""Impulse engine v2, round 2: the SEQUENTIAL leader -> follower machine.

Spec: docs/impulsos-v2.md §R2 (`impulse-2.1.0`, `model: "sequential"`). Owner
decisions 1-4 (2026-11-01): PRO 4h (+ PRO read on 1d), 1300 USDT, 5x cross,
RE-BUYS; the strategy is not a vote — Konkorde (`verde`) and BBWP LEAD, AO /
ADX / MACD / RSI CONFIRM inside a window fitted on IS (lead-time study); exit
by the owner's rule (BBWP red turn + verde zero cross against), a WIDE
invalidation on close (wider of the setup range and 3 ATR), `phase_lost`
only with verde against, time stop at 60 candles; no 1.5 ATR stop. ML RSI
(owner decision 4) is a regime gate in the H2 variant.

Everything reads indicator COLUMNS of CLOSED candles (spec §0.1). Event
arrays are vectorised and causal; only the state machine iterates, so a
replay is O(n) and truncating the future never changes a past decision. The
machine is driven bar by bar (`SequentialMachine.step`) so a ledger can feed
back the realised equity for sizing; `run()` is the constant-equity replay.

Additive: `impulse_service.ImpulseEngine` dispatches here when
`params.model == "sequential"`; the round-1 vote path is untouched.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from . import impulse_service as base
from .ml_rsi import MlRsiParams, ml_rsi_frame, regime_series

FAMILIES: Tuple[str, ...] = ("ao", "adx", "macd", "rsi")
STATES = ("flat", "alert", "in_position")
ACTIONS = ("none", "alert", "enter", "hold", "add_layer", "exit")

# PRO profile for the machine (spec §R2.c / §R2.e): same book parameters on the
# 4h trigger (guardian 1d) and on the 1d read (guardian 1w). Kept apart from
# `trade_profiles.TRADE_PROFILES` (round-1 ATR-stop profiles, API contract).
SEQUENTIAL_PROFILES: Dict[str, Dict[str, Any]] = {
    "pro": {"trigger_tf": "4h", "confirm_tf": "1d", "context_tfs": ("1d", "1w"),
            "window_bounds": (2, 8), "window_default": 4},
    "pro_1d": {"trigger_tf": "1d", "confirm_tf": "1w", "context_tfs": ("1w", "1M"),
               "window_bounds": (2, 6), "window_default": 3},
}

# Follower windows fitted on IS 2024-11-01 -> 2025-12-31 (docs/impulsos-v2-lead-time.md,
# §R2.b formula W_f = clamp(ceil(p75(lag_f)), lo, hi); adx on 1d had 6 pairs -> default 3).
# FROZEN before the round-2 backtest (docs/PREREG_IMPULSOS_v2_r2.md).
FITTED_WINDOWS: Dict[str, Dict[str, int]] = {
    "pro": {"ao": 2, "adx": 4, "macd": 3, "rsi": 2},
    "pro_1d": {"ao": 3, "adx": 3, "macd": 2, "rsi": 5},
}


def sequential_params(profile: str = "pro", **overrides: Any) -> "base.ImpulseParams":
    """`ImpulseParams` of the 2.1.0 sequential rule doc for a SEQUENTIAL_PROFILES entry."""
    try:
        cfg = SEQUENTIAL_PROFILES[profile]
    except KeyError as exc:
        raise ValueError(f"Unknown sequential profile: {profile!r} (use one of {sorted(SEQUENTIAL_PROFILES)})") from exc
    values: Dict[str, Any] = {
        "profile": profile, "model": "sequential",
        "trigger_tf": cfg["trigger_tf"], "confirm_tf": cfg["confirm_tf"], "context_tfs": tuple(cfg["context_tfs"]),
        "confirm_window_bars": dict(FITTED_WINDOWS[profile]),
        "window_default": cfg["window_default"],
        "atr_mult_stop": None,  # §R2.d: no ATR stop
        "time_stop_bars": 60,
    }
    values.update(overrides)
    return base.ImpulseParams(**values)


# ---------------------------------------------------------------------------
# Event derivation (vectorised, causal)
# ---------------------------------------------------------------------------

def _cross_up(a: pd.Series, b: Any) -> pd.Series:
    b_prev = b.shift(1) if isinstance(b, pd.Series) else b
    return ((a.shift(1) <= b_prev) & (a > b)).fillna(False)


def _cross_down(a: pd.Series, b: Any) -> pd.Series:
    b_prev = b.shift(1) if isinstance(b, pd.Series) else b
    return ((a.shift(1) >= b_prev) & (a < b)).fillna(False)


def _regime_from_column(col: pd.Series) -> np.ndarray:
    """Golden/test override: `ml_rsi_regime` as green/red/gray strings or +1/-1/0."""
    mapping = {"green": 1.0, "red": -1.0, "gray": 0.0, "1": 1.0, "-1": -1.0, "0": 0.0, "1.0": 1.0, "-1.0": -1.0, "0.0": 0.0}
    return np.array([mapping.get(str(v).lower(), np.nan) if v is not None else np.nan for v in col.tolist()], dtype=float)


def derive_sequential(df: pd.DataFrame, timeframe: str, p: "base.ImpulseParams") -> "base._Derived":
    """Round-1 derivation + the §R2.b event arrays, family votes and the ML RSI regime."""
    d = base._derive(df, timeframe, p)
    n = d.n
    idx = pd.RangeIndex(n)
    edge = pd.Series(d["edge"], index=idx)
    media = base._col(df, "konkorde_media")
    bbwp = pd.Series(d["bbwp"], index=idx)
    ao = pd.Series(d["ao"], index=idx)
    plus_di, minus_di = base._col(df, "plus_di"), base._col(df, "minus_di")
    macd, macd_signal = base._col(df, "macd"), base._col(df, "macd_signal")
    rsi = base._col(df, "rsi14")

    k_cross_up = pd.Series(d["edge_cross_up_ev"], index=idx)
    k_cross_down = pd.Series(d["edge_cross_down_ev"], index=idx)
    k_turn_up = _cross_up(edge, media)
    k_turn_down = _cross_down(edge, media)
    leader_k = np.sign(k_cross_up.astype(int) + k_turn_up.astype(int) - k_cross_down.astype(int) - k_turn_down.astype(int))

    bb_prev = bbwp.shift(1)
    compression = bbwp.rolling(p.compression_lookback, min_periods=1).min() <= p.bbwp_compression_max
    ignition_ev = ((bb_prev <= p.bbwp_expansion_min) & (bbwp > p.bbwp_expansion_min) & compression).fillna(False)

    ao_d1 = ao - ao.shift(1)
    ao_d0 = ao.shift(1) - ao.shift(2)
    events: Dict[str, pd.Series] = {
        "ao_zero_cross_up": _cross_up(ao, 0.0),
        "ao_zero_cross_down": _cross_down(ao, 0.0),
        "ao_turn_up": ((ao_d1 > 0) & (ao_d0 <= 0)).fillna(False),
        "ao_turn_down": ((ao_d1 < 0) & (ao_d0 >= 0)).fillna(False),
        "macd_cross_up": _cross_up(macd, macd_signal),
        "macd_cross_down": _cross_down(macd, macd_signal),
        "rsi_cross_50_up": _cross_up(rsi, p.rsi_mid),
        "rsi_cross_50_down": _cross_down(rsi, p.rsi_mid),
        "rsi_exit_oversold": ((rsi.shift(1) < p.rsi_oversold) & (rsi >= p.rsi_oversold)).fillna(False),
        "rsi_exit_overbought": ((rsi.shift(1) > p.rsi_overbought) & (rsi <= p.rsi_overbought)).fillna(False),
    }
    turn_state = pd.Series(d["adx_turn_up"], index=idx).astype(bool)
    turn_onset = turn_state & ~turn_state.shift(1, fill_value=False)
    events["adx_turn_up_long"] = (turn_onset & (plus_di > minus_di)).fillna(False)
    events["adx_turn_up_short"] = (turn_onset & (minus_di > plus_di)).fillna(False)

    sides = {"ao_zero_cross_up": 1, "ao_zero_cross_down": -1, "ao_turn_up": 1, "ao_turn_down": -1,
             "adx_turn_up_long": 1, "adx_turn_up_short": -1, "macd_cross_up": 1, "macd_cross_down": -1,
             "rsi_cross_50_up": 1, "rsi_cross_50_down": -1, "rsi_exit_oversold": 1, "rsi_exit_overbought": -1}
    family_of = {name: name.split("_")[0] for name in sides}
    votes: Dict[str, np.ndarray] = {}
    for fam in FAMILIES:
        total = np.zeros(n, dtype=int)
        for name, side in sides.items():
            if family_of[name] == fam:
                total += side * events[name].to_numpy(dtype=int)
        votes[fam] = np.sign(total)

    if "ml_rsi_regime" in df.columns:
        mlrsi = _regime_from_column(df["ml_rsi_regime"])
    elif p.model == "sequential" and "close" in df.columns:
        mp = MlRsiParams(rsi_period=p.mlrsi_rsi_period, alma_window=p.mlrsi_alma_window,
                         alma_sigma=p.mlrsi_alma_sigma, alma_offset=p.mlrsi_alma_offset,
                         threshold_method=p.mlrsi_threshold_method, max_points=p.mlrsi_max_points)
        mlrsi = regime_series(ml_rsi_frame(pd.Series(d["close"]), mp, mode="causal")).to_numpy(dtype=float)
    else:
        mlrsi = np.full(n, np.nan)

    d.arrays.update({
        "media": media.to_numpy(dtype=float),
        "k_cross_up": k_cross_up.to_numpy(dtype=bool), "k_cross_down": k_cross_down.to_numpy(dtype=bool),
        "k_turn_up": k_turn_up.to_numpy(dtype=bool), "k_turn_down": k_turn_down.to_numpy(dtype=bool),
        "leader_k": leader_k.to_numpy(dtype=int), "ignition_ev": ignition_ev.to_numpy(dtype=bool),
        "rsi": rsi.to_numpy(dtype=float), "mlrsi": mlrsi,
        **{f"ev_{k}": v.to_numpy(dtype=bool) for k, v in events.items()},
        **{f"vote_{fam}": v for fam, v in votes.items()},
    })
    d.arrays["_event_sides"] = sides  # type: ignore[assignment]
    return d


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

@dataclass
class Alert:
    bar: int
    side: int  # +1 / -1 / 0 (undecided, bbwp_ignition origin)
    origin: str  # konkorde | bbwp
    confirms: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # family -> {side, bar, event}


@dataclass
class Layer:
    bar: int
    price: float
    notional_usdt: float
    qty: float


@dataclass
class Position:
    side: int
    layers: List[Layer]
    invalidation: float
    invalidation_source: str
    one_r_usdt: float
    e0: float
    alert_bar: int
    entry_bar: int
    last_layer_bar: int

    @property
    def qty(self) -> float:
        return sum(l.qty for l in self.layers)

    @property
    def total_notional(self) -> float:
        return sum(l.notional_usdt for l in self.layers)

    @property
    def avg_entry(self) -> float:
        q = self.qty
        return self.total_notional / q if q > 0 else float("nan")

    def unrealized(self, price: float) -> float:
        return self.side * sum(l.qty * (price - l.price) for l in self.layers)

    @property
    def open_risk(self) -> float:
        return sum(l.qty * abs(l.price - self.invalidation) for l in self.layers)

    def exposure(self, price: float, equity: float) -> float:
        return self.qty * price / equity if equity > 0 else float("inf")

    def liquidation_price(self, equity: float, mmr: float) -> Optional[float]:
        q, a = self.qty, self.avg_entry
        if q <= 0 or not math.isfinite(a):
            return None
        if self.side == 1:
            price = (q * a - equity) / (q * (1.0 - mmr))
            return price if price > 0 else None
        return (equity + q * a) / (q * (1.0 + mmr))


# ---------------------------------------------------------------------------
# Machine
# ---------------------------------------------------------------------------

class SequentialMachine:
    """FLAT -> ALERT -> IN_POSITION -> FLAT over CLOSED trigger candles (spec §R2.b-d).

    `step(i, equity)` decides candle `i`; `equity` (realised wallet, USDT) is
    the sizing base of a new trade (`E0`) and of the liquidation estimate. A
    ledger may call `force_flat(i, reason)` on an intrabar liquidation and
    `force_enter(i, side)` for the anchored replay of §R2.g.
    """

    def __init__(self, params: "base.ImpulseParams", frames: Mapping[str, pd.DataFrame], *,
                 equity: Optional[float] = None) -> None:
        if params.model != "sequential":
            raise ValueError("SequentialMachine needs params.model == 'sequential'")
        self.p = params
        self.engine = base.ImpulseEngine(params)
        if frames.get(params.trigger_tf) is None or not len(frames[params.trigger_tf]):
            raise ValueError(f"Missing trigger frame {params.trigger_tf!r}")
        self.trig = derive_sequential(frames[params.trigger_tf], params.trigger_tf, params)
        self.contexts: Dict[str, base._Derived] = {}
        for tf in params.context_order():
            df = frames.get(tf)
            if df is not None and len(df):
                self.contexts[tf] = base._derive(df, tf, params)
        self.ctx_idx: Dict[str, np.ndarray] = {}
        for tf, d in self.contexts.items():
            if self.trig.close_ms is not None and d.close_ms is not None:
                self.ctx_idx[tf] = np.searchsorted(d.close_ms, self.trig.close_ms, side="right") - 1
            else:  # goldens without timestamps: the caller aligned the last context row
                self.ctx_idx[tf] = np.full(self.trig.n, d.n - 1, dtype=int)
        self.windows = {fam: int(params.confirm_window_bars.get(fam, params.window_default)) for fam in FAMILIES}
        self.ttl = int(params.alert_ttl_bars) if params.alert_ttl_bars else max(self.windows.values())
        self.equity = float(equity if equity is not None else params.equity_usdt)
        self.alert: Optional[Alert] = None
        self.pos: Optional[Position] = None
        self.exit_bar = -1
        self.decisions: List[base.ImpulseDecision] = []

    # -- public ------------------------------------------------------------------
    @property
    def state(self) -> str:
        return "in_position" if self.pos else ("alert" if self.alert else "flat")

    def run(self, *, warmup: int = 0) -> List[base.ImpulseDecision]:
        return [self.step(i) for i in range(max(int(warmup), 0), self.trig.n)]

    def step(self, i: int, equity: Optional[float] = None) -> base.ImpulseDecision:
        if equity is not None:
            self.equity = float(equity)
        dec = self._base(i)
        if self.pos is not None:
            if not self._exit_check(i, dec):
                self._rebuy(i, dec)
        else:
            self._flat_or_alert(i, dec)
        self._stamp(i, dec)
        self.decisions.append(dec)
        return dec

    def force_flat(self, i: int, reason: str) -> None:
        """The ledger liquidated the book intrabar: the machine goes FLAT at candle i."""
        self.pos, self.alert, self.exit_bar = None, None, i

    def force_enter(self, i: int, side: str, equity: Optional[float] = None) -> base.ImpulseDecision:
        """Anchored replay (§R2.g.4): layer 1 at candle i's close with the §R2.c sizing
        and the §R2.d invalidation (`a = e = i`), ignoring confirmations and gates."""
        if equity is not None:
            self.equity = float(equity)
        if self.pos is not None:
            raise RuntimeError("force_enter on an open position")
        dec = self._base(i)
        self.alert = None
        self._enter(i, base.SIDE_VALUES[side], dec, alert_bar=i, confirms={})
        dec.reasons.append("forced_anchor")
        self._stamp(i, dec)
        self.decisions.append(dec)
        return dec

    # -- helpers -----------------------------------------------------------------
    def _ctx_pos(self, i: int) -> Dict[str, int]:
        return {tf: int(idx[i]) for tf, idx in self.ctx_idx.items()}

    def _base(self, i: int) -> base.ImpulseDecision:
        p, T = self.p, self.trig
        info, bias = self.engine._context(self.contexts, self._ctx_pos(i))
        candle_close = None
        if T.close_ms is not None:
            from datetime import datetime, timezone
            candle_close = datetime.fromtimestamp(int(T.close_ms[i]) / 1000.0, tz=timezone.utc).isoformat()
        regime = base._f(T["mlrsi"], i)
        return base.ImpulseDecision(
            timestamp=int(T.open_ms[i]) if T.open_ms is not None else None,
            timeframe=T.timeframe, profile=p.profile, side="none", phase=str(T["phase"][i]), action="none",
            side_score=None, context_bias=bias, candle_close=candle_close, rule_version=p.rule_version,
            mlrsi_regime={1.0: "green", -1.0: "red", 0.0: "gray"}.get(regime) if regime is not None else None,
            equity_usdt=round(self.equity, 4),
            context={
                "band": "low_tf" if T.low_band else "high_tf", "guardian": p.confirm_tf, "model": "sequential",
                "konkorde_line": p.konkorde_line,
                "events": self._events_on(i),
                "values": {"close": base._f(T["close"], i), "bbwp": base._f(T["bbwp"], i), "verde": base._f(T["edge"], i),
                           "media": base._f(T["media"], i), "atr14": base._f(T["atr"], i), "rsi14": base._f(T["rsi"], i)},
                "windows": dict(self.windows), "alert_ttl_bars": self.ttl,
                "timeframes": info,
            },
        )

    def _events_on(self, i: int) -> List[str]:
        T, p = self.trig, self.p
        out: List[str] = []
        if T["k_cross_up"][i]:
            out.append(p.konkorde_code("zero_cross_up"))
        if T["k_cross_down"][i]:
            out.append(p.konkorde_code("zero_cross_down"))
        if T["k_turn_up"][i]:
            out.append(p.konkorde_code("turn_up"))
        if T["k_turn_down"][i]:
            out.append(p.konkorde_code("turn_down"))
        if T["ignition_ev"][i]:
            out.append("bbwp_ignition")
        if T["red_drop_ev"][i]:
            out.append("bbwp_red_turn")
        for name in T.arrays["_event_sides"]:  # type: ignore[union-attr]
            if T[f"ev_{name}"][i]:
                out.append(name)
        return out

    def _family_event(self, fam: str, i: int, side: int) -> Optional[str]:
        sides = self.trig.arrays["_event_sides"]  # type: ignore[index]
        for name, s in sides.items():
            if name.split("_")[0] == fam and s == side and self.trig[f"ev_{name}"][i]:
                return name
        return None

    def _votes(self, i: int) -> Dict[str, int]:
        return {fam: int(self.trig[f"vote_{fam}"][i]) for fam in self.p.follower_families}

    def _guardian(self, dec: base.ImpulseDecision) -> Optional[int]:
        return dec.context_bias.get(self.p.confirm_tf)

    def _stamp(self, i: int, dec: base.ImpulseDecision) -> None:
        dec.state = self.state
        if self.alert is not None:
            dec.alert_side = base.SIDE_LABELS[self.alert.side]
            dec.alert_age = i - self.alert.bar
            dec.confirmations = {k: dict(v) for k, v in self.alert.confirms.items()}
        if self.pos is not None:
            close = float(self.trig["close"][i])
            pos = self.pos
            dec.side = base.SIDE_LABELS[pos.side]
            dec.layers = [{"bar": l.bar, "price": l.price, "notional_usdt": round(l.notional_usdt, 4), "qty": l.qty}
                          for l in pos.layers]
            dec.avg_entry = pos.avg_entry
            dec.total_notional_usdt = round(pos.total_notional, 4)
            dec.open_risk_usdt = round(pos.open_risk, 4)
            dec.exposure_x = round(pos.exposure(close, self.equity), 4)
            dec.invalidation_price = pos.invalidation
            dec.invalidation_source = pos.invalidation_source
            dec.one_r_usdt = round(pos.one_r_usdt, 4)
            dec.stop_price = pos.invalidation
            dec.liquidation_price = pos.liquidation_price(self.equity, self.p.maintenance_margin_rate)
            dec.context.update({"bars_held": i - pos.entry_bar, "entry_price": pos.layers[0].price,
                                "unrealized_usdt": round(pos.unrealized(close), 4),
                                "unrealized_r": round(pos.unrealized(close) / pos.one_r_usdt, 4) if pos.one_r_usdt else None})

    # -- FLAT / ALERT ---------------------------------------------------------------
    def _flat_or_alert(self, i: int, dec: base.ImpulseDecision) -> None:
        p, T = self.p, self.trig
        reasons = dec.reasons
        if not math.isfinite(float(T["bbwp"][i])) or not math.isfinite(float(T["edge"][i])):
            if self.alert is not None and i > self.alert.bar + self.ttl:
                self.alert = None
                reasons.append("alert_expired")
            reasons.append("insufficient_data")
            dec.action = "alert" if self.alert else "none"
            return
        lk = int(T["leader_k"][i])
        ign = bool(T["ignition_ev"][i])

        if self.alert is not None and i > self.alert.bar + self.ttl:
            self.alert = None
            reasons.append("alert_expired")

        if self.alert is not None:
            a = self.alert
            if lk != 0 and a.side == -lk:
                self.alert = Alert(i, lk, "konkorde")
                reasons += [p.konkorde_code("zero_cross_up" if lk == 1 else "zero_cross_down")
                            if (T["k_cross_up"][i] or T["k_cross_down"][i]) else p.konkorde_code("turn_up" if lk == 1 else "turn_down"),
                            "alert_replaced_opposite_leader"]
            elif lk != 0 and a.side == 0:
                a.side = lk
                reasons.append("alert_side_from_konkorde")
            elif ign:
                reasons.append("bbwp_ignition_repeat")
        elif i != self.exit_bar:
            if lk != 0:
                self.alert = Alert(i, lk, "konkorde")
                for code, flag in (("zero_cross_up", "k_cross_up"), ("zero_cross_down", "k_cross_down"),
                                   ("turn_up", "k_turn_up"), ("turn_down", "k_turn_down")):
                    if T[flag][i]:
                        reasons.append(p.konkorde_code(code))
                if ign:
                    reasons.append("bbwp_ignition")
            elif ign:
                self.alert = Alert(i, 0, "bbwp")
                reasons.append("bbwp_ignition")
        elif lk != 0 or ign:
            reasons.append("leader_ignored_exit_candle")

        if self.alert is None:
            reasons.append("no_leader")
            dec.action = "none"
            return
        dec.action = "alert"
        self._alert_update(i, dec)

    def _alert_update(self, i: int, dec: base.ImpulseDecision) -> None:
        p, T, a = self.p, self.trig, self.alert
        reasons = dec.reasons
        votes = self._votes(i)
        if a.side == 0:
            directional = [v for v in votes.values() if v != 0]
            if directional and all(v == directional[0] for v in directional):
                a.side = directional[0]
                reasons.append("side_from_follower")
            else:
                reasons.append("alert_side_undecided")
                return
        for fam, v in votes.items():
            if v != 0 and i <= a.bar + self.windows[fam]:
                a.confirms[fam] = {"side": v, "bar": i, "event": self._family_event(fam, i, v)}
        n_same = sum(1 for c in a.confirms.values() if c["side"] == a.side)
        n_opp = sum(1 for c in a.confirms.values() if c["side"] == -a.side)
        if n_opp >= p.n_confirm:
            self.alert = None
            reasons.append("alert_cancelled_contrary")
            dec.action = "none"
            return
        if n_same < p.n_confirm:
            reasons.append("alert_waiting_confirmation")
            return
        bbwp = float(T["bbwp"][i])
        if bbwp <= p.bbwp_expansion_min:
            reasons.append("entry_wait_bbwp_regime")
            return
        if bbwp >= p.bbwp_red_zone:
            reasons.append("entry_blocked_exhaustion")
            return
        guardian = self._guardian(dec)
        if guardian is None:
            reasons.append("context_missing")
            return
        if guardian == -a.side:
            reasons.append("context_against")
            return
        if p.mlrsi_gate:
            regime = base._f(T["mlrsi"], i)
            if regime is None:
                reasons.append("mlrsi_gate_unknown")
                return
            if int(regime) == 0:
                reasons.append("mlrsi_gate_gray")
                return
            if int(regime) == -a.side:
                reasons.append("mlrsi_gate_against")
                return
        confirms = {k: dict(v) for k, v in a.confirms.items() if v["side"] == a.side}
        self.alert = None
        self._enter(i, a.side, dec, alert_bar=a.bar, confirms=confirms)
        dec.confidence = min(1.0, n_same / max(1, len(p.follower_families)))
        reasons.append("context_aligned" if guardian == a.side else "context_neutral")

    # -- ENTER ------------------------------------------------------------------------
    def _enter(self, i: int, side: int, dec: base.ImpulseDecision, *, alert_bar: int, confirms: Dict[str, Any]) -> None:
        p, T = self.p, self.trig
        close = float(T["close"][i])
        atr = float(T["atr"][i])
        lo_idx = max(0, alert_bar - p.invalidation_range_back)
        if side == 1:
            range_level = float(np.nanmin(T["low"][lo_idx: i + 1]))
            atr_level = close - p.invalidation_atr_mult * atr if math.isfinite(atr) and atr > 0 else float("nan")
            candidates = [(range_level, "invalidation_range"), (atr_level, "invalidation_atr")]
            inv, source = min((c for c in candidates if math.isfinite(c[0])), key=lambda c: c[0])
        else:
            range_level = float(np.nanmax(T["high"][lo_idx: i + 1]))
            atr_level = close + p.invalidation_atr_mult * atr if math.isfinite(atr) and atr > 0 else float("nan")
            candidates = [(range_level, "invalidation_range"), (atr_level, "invalidation_atr")]
            inv, source = max((c for c in candidates if math.isfinite(c[0])), key=lambda c: c[0])
        dist = abs(close - inv)
        if not (dist > 0):
            dec.reasons.append("invalidation_invalid")
            dec.action = "alert"
            self.alert = Alert(alert_bar, side, "konkorde")  # keep waiting
            return
        e0 = self.equity
        notional = min(p.layer1_risk_pct / 100.0 * e0 * close / dist, p.layer1_max_exposure_x * e0)
        qty = notional / close
        self.pos = Position(side=side, layers=[Layer(i, close, notional, qty)], invalidation=inv,
                            invalidation_source=source, one_r_usdt=qty * dist, e0=e0,
                            alert_bar=alert_bar, entry_bar=i, last_layer_bar=i)
        dec.action = "enter"
        dec.side = base.SIDE_LABELS[side]
        dec.notional = round(notional, 4)
        dec.confirmations = confirms
        dec.reasons += [f"confirm_{fam}:{c.get('event')}" for fam, c in confirms.items()]
        dec.reasons.append(source)
        if dec.mlrsi_regime:
            dec.reasons.append(f"mlrsi_{dec.mlrsi_regime}")

    # -- IN_POSITION: exits ----------------------------------------------------------
    def _exit_check(self, i: int, dec: base.ImpulseDecision) -> bool:
        p, T, pos = self.p, self.trig, self.pos
        s = pos.side
        close = float(T["close"][i])
        reasons = dec.reasons
        dec.side = base.SIDE_LABELS[s]
        start = max(0, i - p.exit_window_candles + 1)
        drops = [j for j in range(start, i + 1) if bool(T["red_drop_ev"][j])]
        against = "k_cross_down" if s == 1 else "k_cross_up"
        crosses = [j for j in range(start, i + 1) if bool(T[against][j])]
        if drops and crosses and (i in drops or i in crosses):
            reasons += ["exit_rule_jeisson", "exit_bbwp_red_turn", "exit_konkorde_zero_cross_against"]
            return self._exit(i, dec, close, 0.8)
        if (s == 1 and close <= pos.invalidation) or (s == -1 and close >= pos.invalidation):
            reasons.append("exit_invalidation")
            return self._exit(i, dec, close, 1.0)
        bbwp = float(T["bbwp"][i])
        verde = float(T["edge"][i])
        if math.isfinite(bbwp) and bbwp <= p.phase_lost_level:
            if math.isfinite(verde) and verde * s < 0:
                reasons.append("exit_phase_lost")
                return self._exit(i, dec, close, p.phase_lost_confidence)
            if p.phase_lost_requires_verde_against:
                reasons.append("phase_lost_suppressed_verde_favor")
        held = i - pos.entry_bar
        if p.time_stop_bars is not None and held >= int(p.time_stop_bars) and pos.one_r_usdt > 0:
            if pos.unrealized(close) / pos.one_r_usdt < p.time_stop_min_r:
                reasons.append("exit_time_stop")
                return self._exit(i, dec, close, p.time_stop_confidence)
        if bool(drops) != bool(crosses):
            reasons.append("hold_exit_incomplete")
        return False

    def _exit(self, i: int, dec: base.ImpulseDecision, price: float, confidence: float) -> bool:
        dec.action = "exit"
        dec.exit_price = price
        dec.confidence = confidence
        self._stamp(i, dec)  # report the book that is being closed
        self.pos, self.exit_bar = None, i
        return True

    # -- IN_POSITION: re-buys ---------------------------------------------------------
    def _rebuy(self, i: int, dec: base.ImpulseDecision) -> None:
        p, T, pos = self.p, self.trig, self.pos
        s = pos.side
        close = float(T["close"][i])
        reasons = dec.reasons
        dec.action = "hold"
        votes = self._votes(i)
        same = [fam for fam, v in votes.items() if v == s]
        if any(v == -s for v in votes.values()):
            reasons.append("hold_follower_against")
            return
        if not same:
            reasons.append("hold_no_follower_confirm")
            return
        if len(pos.layers) >= p.max_layers:
            reasons.append("add_rejected_max_layers")
            return
        if i - pos.last_layer_bar < p.layer_min_gap_bars:
            reasons.append("add_rejected_min_gap")
            return
        if not pos.unrealized(close) > 0:
            reasons.append("add_rejected_not_in_profit")
            return
        if dec.phase not in ("ignition", "expansion"):
            reasons.append("add_rejected_phase")
            return
        guardian = self._guardian(dec)
        if guardian is None or guardian == -s:
            reasons.append("add_rejected_context")
            return
        notional = p.layer_add_scale * pos.layers[0].notional_usdt
        qty = notional / close
        if pos.open_risk + qty * abs(close - pos.invalidation) > p.max_open_risk_pct / 100.0 * pos.e0 + 1e-9:
            reasons.append("add_rejected_risk_cap")
            return
        if pos.total_notional + notional > p.max_exposure_x * pos.e0 + 1e-9:
            reasons.append("add_rejected_exposure_cap")
            return
        if p.mlrsi_gate:
            regime = base._f(T["mlrsi"], i)
            if regime is None or int(regime) != s:
                reasons.append("add_rejected_mlrsi")
                return
        pos.layers.append(Layer(i, close, notional, qty))
        pos.last_layer_bar = i
        dec.action = "add_layer"
        dec.notional = round(notional, 4)
        reasons.append("add_layer_follower_confirm")
        reasons += [e for e in (self._family_event(fam, i, s) for fam in same) if e]


__all__: Sequence[str] = (
    "FAMILIES", "STATES", "ACTIONS", "SEQUENTIAL_PROFILES", "FITTED_WINDOWS", "sequential_params",
    "derive_sequential", "Alert", "Layer", "Position", "SequentialMachine",
)
