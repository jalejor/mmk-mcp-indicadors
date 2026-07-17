"""Assembly of the additive `monitors` block for rule_version 0.2.0 (spec §I).

Stateless composition layer over the pure detectors in `rule_v020.py`:
per-TF M1 (v2, with the §I.1 color flip) and M1m watches, the H1 hierarchy
(Rule 1 override + Rule 2 p_false boost), M2 contrary-impulse emissions,
E4.1 `vol_turn_rounded` states and the C1 confluence windows.

Only `SetupEvaluationService` calls this, and only when the engine runs with
rule_version "0.2.0" — the v0.1.0 monitor path is untouched. Every block is
ADDITIVE: existing consumers (mmk-api watcher, dashboard) keep parsing
`false_entry_watch` + `tf_status`; the new blocks are new keys.

Emission discipline (addendum 0.3.1 / B.3.5): 15m entries are H1/C1/M2
INPUTS — the F1 watcher must never push them; the 30m M1m runs in SHADOW
(computed + logged, never alerted). Both carry explicit flags so the
consumer cannot mistake them for alertable watches.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas as pd

from .rule_v020 import (
    BAND_UP_MAP,
    CONTRARY_IMPULSE_DEFAULTS,
    FALSE_ENTRY_V2_DEFAULTS,
    FALSE_IGNITION_15M,
    FALSE_IGNITION_30M_SHADOW,
    FE_CONFIRMED_BY_HIGHER_TF,
    FE_FALSE_ENTRY_CONFIRMED,
    FI_CONFIRMED,
    FI_FALSE_IGNITION_PROBABLE,
    FI_WATCHING,
    FI_WHIPSAW,
    LADDER_V020,
    PROFILE_BY_TF,
    boosted_p_false,
    contrary_impulse,
    di_color_at,
    evaluate_confluence,
    false_entry_state_v2,
    false_ignition_state,
    higher_confirmed_source,
    p_false_boosts,
    vol_turn_rounded_variant,
)
from .setup_service import (
    FE_CONFIRMED,
    FE_FALSE_ENTRY_PROBABLE,
    FE_WATCHING,
    FE_WHIPSAW,
    TIMEFRAME_SECONDS,
)

# AO-anchored M1 timeframes under v0.2.0: 15m is M1m-only (addendum B.3.5).
M1_TFS_V020 = ("30m", "1h", "4h", "1d", "1w")
# M1m anchors: 15m ON, 30m SHADOW, >=1h OFF (addendum B.3.5).
M1M_PARAMS_BY_TF = {"15m": FALSE_IGNITION_15M, "30m": FALSE_IGNITION_30M_SHADOW}
# Same terminal-visibility rule as the v0.1.0 block (setup_evaluation_service).
TERMINAL_MAX_AGE = 6

_COLOR_TO_DIRECTION = {"bullish": "up", "bearish": "down"}
_OPPOSITE = {"up": "down", "down": "up"}


def build_monitors_v020(
    frames: Dict[str, pd.DataFrame],
    ensure_frame: Callable[[str], pd.DataFrame],
) -> Dict[str, Any]:
    """Build the full v0.2.0 monitors block for one evaluate() call.

    `frames` is the per-call frame memo (mutated to reuse fetches);
    `ensure_frame(tf)` loads an enriched frame or raises. A TF that fails to
    load or evaluate is dropped and reported in `tf_status` — never silently
    skipped (P0 doctrine, 2026-07-13).
    """
    ok_frames, tf_status = _collect_frames(frames, ensure_frame)
    snapshots = _tf_snapshots(ok_frames, tf_status)

    confirmed_map = _confirmed_directions(snapshots)
    vol_moves = {
        tf: snap["move"]
        for tf, snap in snapshots.items()
        if snap["vol_turn"] is not None and snap["move"] is not None
    }

    fe_records = _finalized_m1_records(snapshots, confirmed_map, vol_moves)
    fi_records = _finalized_m1m_records(snapshots, confirmed_map, vol_moves)

    return {
        "false_entry_watch": [
            _fe_entry(record, ok_frames, snapshots)
            for record in fe_records
            if _should_emit_fe(record)
        ],
        "tf_status": tf_status,
        "false_ignition_watch": [
            _fi_entry(record, ok_frames)
            for record in fi_records
            if _should_emit_fi(record)
        ],
        "contrary_impulse": _contrary_entries(
            fe_records + fi_records, snapshots, ok_frames
        ),
        "confluence": evaluate_confluence(ok_frames),
        "vol_turn_rounded": [
            {"timeframe": tf, "variant": snap["vol_turn"], "move_direction": snap["move"]}
            for tf, snap in snapshots.items()
            if snap["vol_turn"] is not None
        ],
    }


# ---------------------------------------------------------------------------
# Frame collection + per-TF raw states
# ---------------------------------------------------------------------------

def _collect_frames(
    frames: Dict[str, pd.DataFrame],
    ensure_frame: Callable[[str], pd.DataFrame],
) -> Tuple[Dict[str, pd.DataFrame], Dict[str, str]]:
    ok: Dict[str, pd.DataFrame] = {}
    tf_status: Dict[str, str] = {}
    for tf in LADDER_V020:
        try:
            frame = frames.get(tf)
            if frame is None:
                frame = ensure_frame(tf)
                frames[tf] = frame  # memoise within this evaluate() call
            if frame.empty:
                tf_status[tf] = "failed:empty_frame"
                continue
            ok[tf] = frame
            tf_status[tf] = "ok"
        except Exception as exc:  # a bad TF must not break evaluate — but is REPORTED
            tf_status[tf] = _failure(exc)
    return ok, tf_status


def _failure(exc: Exception) -> str:
    return f"failed:{type(exc).__name__}: {exc}".replace("\n", " ").strip()


def _tf_snapshots(
    ok_frames: Dict[str, pd.DataFrame], tf_status: Dict[str, str]
) -> Dict[str, Dict[str, Any]]:
    snapshots: Dict[str, Dict[str, Any]] = {}
    for tf in list(ok_frames):
        try:
            snapshots[tf] = _tf_snapshot(tf, ok_frames[tf])
        except Exception as exc:  # evaluation failure = blind TF -> tf_status
            tf_status[tf] = _failure(exc)
            ok_frames.pop(tf)
    return snapshots


def _tf_snapshot(tf: str, frame: pd.DataFrame) -> Dict[str, Any]:
    snap: Dict[str, Any] = {"m1": {}, "m1m": {}, "vol_turn": None, "move": None}
    if tf in M1_TFS_V020:
        for direction in ("up", "down"):
            snap["m1"][direction] = false_entry_state_v2(
                frame.get("ao"), frame.get("adx14"),
                frame.get("plus_di"), frame.get("minus_di"),
                direction=direction, params=FALSE_ENTRY_V2_DEFAULTS,
            )
    m1m_params = M1M_PARAMS_BY_TF.get(tf)
    if m1m_params is not None:
        for direction in ("up", "down"):
            snap["m1m"][direction] = false_ignition_state(
                frame.get("ao"), frame.get("adx14"),
                frame.get("plus_di"), frame.get("minus_di"), frame.get("bbwp"),
                direction=direction, params=m1m_params,
            )
    bbwp = frame.get("bbwp")
    if bbwp is not None:
        snap["vol_turn"] = vol_turn_rounded_variant(bbwp)
        if snap["vol_turn"] is not None:
            color = di_color_at(frame.get("plus_di"), frame.get("minus_di"))
            snap["move"] = _COLOR_TO_DIRECTION.get(color)
    return snap


def _confirmed_directions(snapshots: Dict[str, Dict[str, Any]]) -> Dict[str, Tuple[str, ...]]:
    """H1 Rule-1 sources: directions with an M1 (or M1m) CONFIRMED per TF."""
    confirmed: Dict[str, Tuple[str, ...]] = {}
    for tf, snap in snapshots.items():
        dirs = [d for d, fe in snap["m1"].items() if fe.state == FE_CONFIRMED]
        dirs += [
            d for d, fi in snap["m1m"].items()
            if fi.state == FI_CONFIRMED and d not in dirs
        ]
        if dirs:
            confirmed[tf] = tuple(dirs)
    return confirmed


# ---------------------------------------------------------------------------
# H1 finalization (Rule 1 override, Rule 2 boost) into watch records
# ---------------------------------------------------------------------------

def _finalized_m1_records(
    snapshots: Dict[str, Dict[str, Any]],
    confirmed_map: Dict[str, Tuple[str, ...]],
    vol_moves: Dict[str, str],
) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for tf, snap in snapshots.items():
        for direction, fe in snap["m1"].items():
            if fe.state is None:
                continue
            record = {
                "kind": "m1", "timeframe": tf, "direction": direction,
                "raw": fe, "state": fe.state, "p_false": fe.p_false,
                "boosts": [], "higher_tf": None,
            }
            if fe.state in (FE_FALSE_ENTRY_PROBABLE, FE_FALSE_ENTRY_CONFIRMED):
                _apply_hierarchy(record, confirmed_map, vol_moves)
            records.append(record)
    return records


def _finalized_m1m_records(
    snapshots: Dict[str, Dict[str, Any]],
    confirmed_map: Dict[str, Tuple[str, ...]],
    vol_moves: Dict[str, str],
) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for tf, snap in snapshots.items():
        for direction, fi in snap["m1m"].items():
            if fi.state is None:
                continue
            record = {
                "kind": "m1m", "timeframe": tf, "direction": direction,
                "raw": fi, "state": fi.state, "p_false": fi.p_false_ignition,
                "boosts": [], "higher_tf": None,
            }
            if fi.state == FI_FALSE_IGNITION_PROBABLE:
                _apply_hierarchy(record, confirmed_map, vol_moves)
            records.append(record)
    return records


def _apply_hierarchy(
    record: Dict[str, Any],
    confirmed_map: Dict[str, Tuple[str, ...]],
    vol_moves: Dict[str, str],
) -> None:
    """Rule 1 first (and it always wins); Rule 2 only when Rule 1 is silent."""
    source = higher_confirmed_source(
        record["timeframe"], record["direction"], confirmed_map
    )
    if source is not None:
        record["state"] = FE_CONFIRMED_BY_HIGHER_TF
        record["higher_tf"] = {"source_tf": source}
        record["p_false"] = None
        return
    boosts = p_false_boosts(record["timeframe"], record["direction"], vol_moves)
    if boosts and record["p_false"] is not None:
        record["boosts"] = boosts
        record["p_false"] = boosted_p_false(record["p_false"], boosts)


# ---------------------------------------------------------------------------
# Serialization + emission gating
# ---------------------------------------------------------------------------

def _candle_close_ts(frame: pd.DataFrame, timeframe: str, age: int) -> str:
    open_ts = frame.index[-1 - age]
    return (open_ts + pd.Timedelta(seconds=TIMEFRAME_SECONDS[timeframe])).isoformat()


def _should_emit_fe(record: Dict[str, Any]) -> bool:
    """Active watches always; terminal states only while fresh (<= 6 candles),
    so the scheduler catches the adjudication and stale crosses drop off."""
    fe = record["raw"]
    state = record["state"]
    if state == FE_WATCHING:
        return True
    confirm = FALSE_ENTRY_V2_DEFAULTS.confirm_candles
    if state == FE_CONFIRMED:
        terminal_age = fe.adx_turn["age"] if fe.adx_turn else 0
    elif state == FE_WHIPSAW:
        terminal_age = fe.whipsaw_age if fe.whipsaw_age is not None else 0
    elif state == FE_FALSE_ENTRY_CONFIRMED:
        terminal_age = fe.event_age - (fe.color_flip_age or 0)
    elif state == FE_CONFIRMED_BY_HIGHER_TF:
        terminal_age = fe.event_age - (fe.color_flip_age or confirm)
    else:  # FALSE_ENTRY_PROBABLE
        terminal_age = fe.event_age - confirm
    return terminal_age <= TERMINAL_MAX_AGE


def _should_emit_fi(record: Dict[str, Any]) -> bool:
    fi = record["raw"]
    state = record["state"]
    if state == FI_WATCHING:
        return True
    if state == FI_CONFIRMED:
        # follow_age counts candles AFTER t0; the event's age from the last
        # closed candle is t0_age - follow_age.
        terminal_age = (
            fi.t0_age - fi.follow_age if fi.follow_age is not None else 0
        )
    elif state == FI_WHIPSAW:
        terminal_age = fi.whipsaw_age if fi.whipsaw_age is not None else 0
    else:  # FALSE_IGNITION_PROBABLE or CONFIRMED_BY_HIGHER_TF
        confirm = M1M_PARAMS_BY_TF[record["timeframe"]].confirm_candles
        terminal_age = fi.t0_age - confirm
    return terminal_age <= TERMINAL_MAX_AGE


def _fe_entry(
    record: Dict[str, Any],
    ok_frames: Dict[str, pd.DataFrame],
    snapshots: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    fe = record["raw"]
    tf = record["timeframe"]
    return {
        "timeframe": tf,
        "direction": record["direction"],
        "state": record["state"],
        "early_warning": fe.early_warning,
        "event_age": fe.event_age,
        "consecutive_ao_candles": fe.consecutive_ao_candles,
        "adx_turn": fe.adx_turn,
        "p_false": record["p_false"],
        "cross_candle_ts": _candle_close_ts(ok_frames[tf], tf, fe.event_age),
        "color_flip_age": fe.color_flip_age,
        "p_false_boosts": record["boosts"],
        "higher_tf": record["higher_tf"],
        "ignition_from_below": _ignition_from_below(record, snapshots),
    }


def _fi_entry(record: Dict[str, Any], ok_frames: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
    fi = record["raw"]
    tf = record["timeframe"]
    return {
        "timeframe": tf,
        "direction": record["direction"],
        "state": record["state"],
        "t0_age": fi.t0_age,
        "adx_turn": fi.adx_turn,
        "confirmed_by": fi.confirmed_by,
        "follow_age": fi.follow_age,
        "whipsaw_age": fi.whipsaw_age,
        "p_false_ignition": record["p_false"],
        "p_false_boosts": record["boosts"],
        "higher_tf": record["higher_tf"],
        # 30m M1m is a SHADOW anchor (never alerted); 15m is input-only for
        # H1/C1/M2 (never pushed) — addendum B.3.5 emission discipline.
        "shadow": tf == "30m",
        "alertable": False,
        "t0_candle_ts": _candle_close_ts(ok_frames[tf], tf, fi.t0_age),
    }


def _ignition_from_below(
    record: Dict[str, Any], snapshots: Dict[str, Dict[str, Any]]
) -> bool:
    """Addendum B.3.3 downward ignition flag: a 1h WATCHING watch with BOTH
    15m and 30m confirmed in the same direction (fresh, terminal age <= 6).
    Flag only — it never auto-confirms the 1h (replay Q21 decides upgrades)."""
    if record["timeframe"] != "1h" or record["state"] != FE_WATCHING:
        return False
    direction = record["direction"]
    return _fresh_confirmed(snapshots.get("15m"), direction) and _fresh_confirmed(
        snapshots.get("30m"), direction
    )


def _fresh_confirmed(snap: Optional[Dict[str, Any]], direction: str) -> bool:
    if snap is None:
        return False
    fe = snap["m1"].get(direction)
    if fe is not None and fe.state == FE_CONFIRMED and fe.adx_turn:
        if fe.adx_turn["age"] <= TERMINAL_MAX_AGE:
            return True
    fi = snap["m1m"].get(direction)
    if fi is None or fi.state != FI_CONFIRMED or fi.follow_age is None:
        return False
    return (fi.t0_age - fi.follow_age) <= TERMINAL_MAX_AGE


# ---------------------------------------------------------------------------
# M2 contrary_impulse entries (spec §I.2)
# ---------------------------------------------------------------------------

def _contrary_entries(
    records: List[Dict[str, Any]],
    snapshots: Dict[str, Dict[str, Any]],
    ok_frames: Dict[str, pd.DataFrame],
) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    for record in records:
        if record["state"] not in (
            FE_FALSE_ENTRY_PROBABLE, FE_FALSE_ENTRY_CONFIRMED, FI_FALSE_IGNITION_PROBABLE
        ):
            continue
        entry = _m2_entry(record, snapshots, ok_frames)
        if entry is not None:
            entries.append(entry)
    return entries


def _adjudication_age(record: Dict[str, Any]) -> Optional[int]:
    raw = record["raw"]
    if record["kind"] == "m1m":
        confirm = M1M_PARAMS_BY_TF[record["timeframe"]].confirm_candles
        return raw.t0_age - confirm
    if record["state"] == FE_FALSE_ENTRY_CONFIRMED:
        return raw.event_age - (raw.color_flip_age or 0)
    return raw.event_age - FALSE_ENTRY_V2_DEFAULTS.confirm_candles


def _confirmed_age(snap: Optional[Dict[str, Any]], direction: str) -> Optional[int]:
    """Age the (M1 or M1m) contrary CONFIRMED fired at, for M2 trigger (b)."""
    if snap is None:
        return None
    fe = snap["m1"].get(direction)
    if fe is not None and fe.state == FE_CONFIRMED and fe.adx_turn:
        return fe.adx_turn["age"]
    fi = snap["m1m"].get(direction)
    if fi is not None and fi.state == FI_CONFIRMED and fi.follow_age is not None:
        return fi.t0_age - fi.follow_age  # event age from the last closed candle
    return None


def _m2_entry(
    record: Dict[str, Any],
    snapshots: Dict[str, Dict[str, Any]],
    ok_frames: Dict[str, pd.DataFrame],
) -> Optional[Dict[str, Any]]:
    tf = record["timeframe"]
    direction = record["direction"]
    adjudication_age = _adjudication_age(record)
    if adjudication_age is None or adjudication_age < 0:
        return None

    contrary_dir = _OPPOSITE[direction]
    higher_ages: Dict[str, Optional[int]] = {}
    same_age = _confirmed_age(snapshots.get(tf), contrary_dir)
    if same_age is not None:
        higher_ages[tf] = same_age
    up_tf = BAND_UP_MAP.get(tf)
    if up_tf is not None:
        up_age = _confirmed_age(snapshots.get(up_tf), contrary_dir)
        if up_age is not None:
            higher_ages[up_tf] = up_age

    frame = ok_frames[tf]
    result = contrary_impulse(
        frame.get("ao"), frame.get("adx14"),
        frame.get("plus_di"), frame.get("minus_di"),
        direction=direction, adjudication_age=adjudication_age,
        higher_confirmed_ages=higher_ages, params=CONTRARY_IMPULSE_DEFAULTS,
    )
    if result is None or result.confirmation_age > TERMINAL_MAX_AGE:
        return None

    raw = record["raw"]
    source: Dict[str, Any] = {
        "kind": record["kind"],
        "state": record["state"],
        "direction": direction,
        "p_false": record["p_false"],
        "adjudication_age": adjudication_age,
    }
    if record["kind"] == "m1":
        source["cross_candle_ts"] = _candle_close_ts(frame, tf, raw.event_age)
    else:
        source["t0_candle_ts"] = _candle_close_ts(frame, tf, raw.t0_age)
    return {
        "timeframe": tf,
        "direction": contrary_dir,
        "profile": PROFILE_BY_TF[tf],
        "trigger": result.trigger,
        "confirmation_age": result.confirmation_age,
        "detail": result.detail,
        "source": source,
    }
