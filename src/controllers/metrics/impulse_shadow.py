"""Impulsos-v2 round 8: FORWARD SHADOW runner (paper, local JSONL, ntfy), long + short.

Protocol: docs/PREREG_IMPULSOS_v2_r8_shadow.md. Every hourly run drives the frozen 2.3.0
snipper chain (`r5_params("snipper", entry_filter)`, book 5x cross) of the 3 entries x 9
assets from the fixed ANCHOR up to the last CLOSED 1h candle. The machine is causal, so a
decision never changes once made: the shadow's state is the JSONL of recorded events and
trades, deduplicated by key, which makes a repeated run a no-op. Each ENTER is labelled with
the two regime identifiers of `impulse_regime` at its trigger close.

Incremental runner (2026-11-02, byte-identical to the full replay — `scripts/shadow_r8_parity.py`):

* the OHLCV cache only fetches candles that can already be closed;
* each asset is enriched ONCE (`IndicatorsService.calculate_impulse`: the columns the
  machine reads, same functions / parameters as `calculate_all`) and the three entries share
  the derived arrays (`SequentialMachine(derived_from=...)`);
* the ML RSI percentile thresholds (trailing 3000-bar window, causal) are cached per
  asset / TF and only computed for new candles (`ml_rsi_cached`);
* machine + ledger are saved per (entry, asset) at the candle BEFORE the last one and resumed
  from there when the frame prefix they were built on is unchanged (sha256 of the raw OHLCV up
  to that candle, trigger and contexts); the last candle is always re-driven because an
  `enter` on the last candle is not filled (`entry_skipped_last_candle`). Any mismatch falls
  back to the full replay from the anchor, which is the same code path.

Additive and isolated: nothing here is imported by the live API; no Mongo, no Telegram, no
exchange keys (public spot OHLCV through the same `MarketDataService` the backtests use).
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from .impulse_backtest import (
    TIMEFRAME_MS,
    WARMUP_BARS,
    Layer as LedgerLayer,
    SequentialDriver,
    bitget_history_fetcher,
    closed_only,
    fetch_ohlcv_forward,
    ledger_for,
    rows_to_frame,
    utc,
)
from .impulse_regime import RegimeSeries, book_of, decision_ms, label_signal, regime_series
from .impulse_sequential import Alert, Layer as MachineLayer, Position, SequentialMachine, r5_params
from .impulse_service import _open_ms
from .ml_rsi import MlRsiParams, alma, regime_of, rsi, thresholds

ROUND = "r8"
RULE_LABEL = "impulse-2.3.0-r8"
PROFILE = "snipper"
EXCHANGE = "bitget"
UNIVERSE: Sequence[str] = ("BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "DOGE/USDT", "NEAR/USDT", "BNB/USDT", "LINK/USDT", "ADA/USDT")
ENTRIES: Dict[str, Optional[str]] = {"base": None, "adx_turn": "adx_turn", "bbwp_fresh_blue": "bbwp_fresh_blue"}
BOOK: Dict[str, Any] = {"leverage": 5.0, "margin_mode": "cross", "maintenance_margin_rate": 0.0056}  # cross5, r6 §6 B
ANCHOR = "2026-10-01T00:00:00+00:00"  # machine + ledger start (prereg §4)
ACTIVATION = "2026-11-01T18:00:00+00:00"  # first decision that counts (prereg §4)
WARMUP: Dict[str, int] = {"1h": 3300, "4h": 3300, "1d": 420}  # ML RSI percentile window 3000 on 1h / 4h
RECORDED_ACTIONS = ("enter", "add_layer", "reduce", "exit")
NOTIFIED_ACTIONS = ("enter", "exit")
BOOKS = ("long_only", "short_only", "regime_own", "regime_btc")
EVENTS_FILE, TRADES_FILE, STATE_FILE = "events.jsonl", "trades.jsonl", "state.json"
CACHE_DIR = "cache"  # <state-dir>/cache: machine snapshots + ML RSI thresholds (derived, rebuildable)
SNAPSHOT_VERSION = 1


def run_key(entry: str) -> str:
    return f"{PROFILE}:{entry}:spec:cross5"


def params_for(entry: str):
    return r5_params(PROFILE, entry_filter=ENTRIES[entry], rule_version=RULE_LABEL, **BOOK)


def iso(ms: int) -> str:
    return datetime.fromtimestamp(int(ms) / 1000.0, tz=timezone.utc).isoformat()


def ms_of(value: Any) -> int:
    return int(pd.Timestamp(value).timestamp() * 1000)


def floor_hour_ms(now_ms: int) -> int:
    return int(now_ms) - int(now_ms) % TIMEFRAME_MS["1h"]


def _json_default(value: Any) -> Any:
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    return str(value)


def write_atomic(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# Incremental OHLCV cache (closed candles only, one JSON per symbol/TF)
# ---------------------------------------------------------------------------

def cache_path(cache_dir: Path, symbol: str, timeframe: str) -> Path:
    return Path(cache_dir) / f"{EXCHANGE}_{symbol.replace('/', '-')}_{timeframe}.json"


def merge_rows(cached: Sequence[Sequence[Any]], fresh: Sequence[Sequence[Any]]) -> List[List[Any]]:
    """Union by open timestamp, the fresh row wins, ascending."""
    by_ts: Dict[int, List[Any]] = {int(r[0]): list(r) for r in cached}
    for r in fresh:
        by_ts[int(r[0])] = list(r)
    return [by_ts[k] for k in sorted(by_ts)]


def load_incremental(symbol: str, timeframe: str, *, since_ms: int, end_ms: int, cache_dir: Path,
                     fetch: Callable[..., List[List[Any]]], fallback: Optional[Callable[..., List[List[Any]]]] = None,
                     now_ms: Optional[int] = None) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Closed candles in [since_ms, end_ms): the cache is extended from its last row, never refetched.

    Nothing is fetched while the candle after the last cached one cannot have closed yet
    (`cursor + timeframe > now`): it would only return the forming candle, which
    `closed_only` drops anyway. The file is rewritten only when its rows change."""
    path = cache_path(cache_dir, symbol, timeframe)
    cached: List[List[Any]] = []
    meta: Dict[str, Any] = {}
    if path.exists():
        meta = json.loads(path.read_text())
        if int(meta.get("since_ms", 1 << 62)) <= since_ms:
            cached = [r for r in meta.get("rows", []) if int(r[0]) >= since_ms]
    cursor = int(cached[-1][0]) + TIMEFRAME_MS[timeframe] if cached else since_ms
    wall_ms = time.time() * 1000.0 if now_ms is None else now_ms
    fetched = 0
    if cursor < end_ms and cursor + TIMEFRAME_MS[timeframe] <= wall_ms:
        fresh = fetch_ohlcv_forward(fetch, symbol=symbol, timeframe=timeframe, since_ms=cursor, end_ms=end_ms, fallback=fallback)
        fetched = sum(1 for r in fresh if int(r[0]) < end_ms)
        cached = merge_rows(cached, fresh)
    df = closed_only(rows_to_frame(cached), timeframe, utc(datetime.fromtimestamp(end_ms / 1000.0, tz=timezone.utc)), now_ms=now_ms)
    rows = df[["timestamp", "open", "high", "low", "close", "volume"]].values.tolist()
    if fetched or len(rows) != len(meta.get("rows", [])) or int(meta.get("since_ms", -1)) != since_ms:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"exchange": EXCHANGE, "symbol": symbol, "timeframe": timeframe, "since_ms": since_ms,
                                    "updated_at": datetime.now(timezone.utc).isoformat(), "rows": rows}))
    info = {"rows": len(rows), "fetched": fetched, "last_open": iso(int(rows[-1][0])) if rows else None}
    return df, info


def exchange_fetchers() -> Tuple[Callable[..., List[List[Any]]], Optional[Callable[..., List[List[Any]]]]]:
    from .market_data_service import MarketDataService

    ex = MarketDataService(exchange_name=EXCHANGE).exchange
    return ex.fetch_ohlcv, bitget_history_fetcher(ex)


def warmup_since_ms(anchor_ms: int, timeframe: str) -> int:
    return int(anchor_ms) - WARMUP.get(timeframe, WARMUP_BARS) * TIMEFRAME_MS[timeframe]


# ---------------------------------------------------------------------------
# Enrichment: the machine's columns, ML RSI thresholds from an incremental cache
# ---------------------------------------------------------------------------

def mlrsi_cache_path(cache_dir: Path, symbol: str, timeframe: str) -> Path:
    return Path(cache_dir) / f"mlrsi_{EXCHANGE}_{symbol.replace('/', '-')}_{timeframe}.npz"


def ml_rsi_cached(close: pd.Series, path: Optional[Path], params: MlRsiParams = MlRsiParams(), *,
                  write: bool = False) -> pd.DataFrame:
    """`ml_rsi.ml_rsi_frame(close, params, mode="causal")`, thresholds only computed for new rows.

    The cache holds the smoothed RSI and both thresholds of a prefix. The prefix is reused
    only when its smoothed values are IDENTICAL (NaN-aware) to the ones recomputed on the
    current series: the trailing window of row j then holds the same numbers, so
    `thresholds` returns the same floats it returned when the cache was written."""
    p = params
    smoothed = alma(rsi(close, p.rsi_period), p.alma_window, p.alma_offset, p.alma_sigma)
    values = smoothed.to_numpy(dtype=float)
    n = len(values)
    upper = np.full(n, np.nan)
    lower = np.full(n, np.nan)
    start = 0
    signature = json.dumps(asdict(p), sort_keys=True)
    if path is not None and path.exists():
        try:
            with np.load(path) as z:
                old_values, old_upper, old_lower, old_sig = z["values"], z["upper"], z["lower"], str(z["params"])
            m = len(old_values)
            if old_sig == signature and m <= n and np.array_equal(old_values, values[:m], equal_nan=True):
                upper[:m], lower[:m] = old_upper, old_lower
                start = m
        except Exception:  # unreadable cache: recompute everything
            start = 0
    for j in range(start, n):
        lower[j], upper[j] = thresholds(values[max(0, j - p.max_points): j + 1], p)
    regime = [regime_of(v, u, lo_) for v, u, lo_ in zip(values, upper, lower)]
    if write and path is not None and start < n:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp.npz")
        np.savez(tmp, values=values, upper=upper, lower=lower, params=np.array(signature))
        os.replace(tmp, path)
    return pd.DataFrame({"ml_rsi": values, "ml_rsi_upper": upper, "ml_rsi_lower": lower, "ml_rsi_regime": regime},
                        index=close.index)


def enrich_impulse(df: pd.DataFrame, *, mlrsi_cache: Optional[Path] = None, write: bool = False) -> pd.DataFrame:
    """`IndicatorsService(bbwp_definition="tv").calculate_impulse()`; ML RSI from the cache when given."""
    from .indicators_service import IndicatorsService

    svc = IndicatorsService(df, bbwp_definition="tv")
    svc.calculate_impulse(ml_rsi=mlrsi_cache is None)
    if mlrsi_cache is not None:
        frame = ml_rsi_cached(svc.df["close"], mlrsi_cache, MlRsiParams(), write=write)
        for col in ("ml_rsi", "ml_rsi_upper", "ml_rsi_lower"):
            svc.df[col] = frame[col].to_numpy()
        svc.df["ml_rsi_regime"] = frame["ml_rsi_regime"].to_numpy(dtype=object)
    return svc.df


def enriched_frames(params: Any, loader: Callable[[str], pd.DataFrame], *, symbol: str = "",
                    cache_dir: Optional[Path] = None, write: bool = False) -> Tuple[Dict[str, pd.DataFrame], Dict[str, str]]:
    """Trigger + context frames enriched for the machine (`impulse_backtest.load_sequential_frames`
    with `enrich_impulse`); a context TF that cannot be loaded degrades to NaN bias."""

    def enrich(tf: str) -> pd.DataFrame:
        path = mlrsi_cache_path(cache_dir, symbol, tf) if cache_dir is not None else None
        return enrich_impulse(loader(tf), mlrsi_cache=path, write=write)

    frames: Dict[str, pd.DataFrame] = {params.trigger_tf: enrich(params.trigger_tf)}
    status: Dict[str, str] = {params.trigger_tf: "ok"}
    for tf in params.context_order():
        try:
            frames[tf] = enrich(tf)
            status[tf] = "ok"
        except Exception as exc:  # context only
            status[tf] = f"failed:{type(exc).__name__}"
    return frames, status


# ---------------------------------------------------------------------------
# Machine + ledger snapshots (resume from the candle before the last one)
# ---------------------------------------------------------------------------

def snapshot_path(cache_dir: Path, entry: str, symbol: str) -> Path:
    return Path(cache_dir) / f"machine_{entry}_{symbol.replace('/', '-')}.json"


def frame_prefix_sha(df: pd.DataFrame, n: int) -> str:
    """sha256 of the raw candles (open ms + OHLCV) of the first `n` rows."""
    h = hashlib.sha256()
    open_ms = _open_ms(df)
    if open_ms is not None:
        h.update(np.ascontiguousarray(open_ms[:n]).tobytes())
    cols = [c for c in ("open", "high", "low", "close", "volume") if c in df.columns]
    h.update(np.ascontiguousarray(df[cols].to_numpy(dtype=float)[:n]).tobytes())
    return h.hexdigest()


def _params_json(params: Any) -> Dict[str, Any]:
    return json.loads(json.dumps(asdict(params), default=_json_default))


def machine_state(m: SequentialMachine) -> Dict[str, Any]:
    return {"alert": asdict(m.alert) if m.alert is not None else None,
            "pos": asdict(m.pos) if m.pos is not None else None,
            "exit_bar": m.exit_bar, "equity": m.equity}


def restore_machine(m: SequentialMachine, state: Mapping[str, Any]) -> None:
    a = state.get("alert")
    m.alert = Alert(bar=int(a["bar"]), side=int(a["side"]), origin=str(a["origin"]),
                    confirms={k: dict(v) for k, v in a["confirms"].items()}) if a else None
    p = state.get("pos")
    if p:
        layers = [MachineLayer(bar=int(l["bar"]), price=float(l["price"]), notional_usdt=float(l["notional_usdt"]), qty=float(l["qty"]))
                  for l in p["layers"]]
        m.pos = Position(**{**{k: v for k, v in p.items() if k != "layers"}, "layers": layers})
    else:
        m.pos = None
    m.exit_bar = int(state["exit_bar"])
    m.equity = float(state["equity"])
    m.decisions = []


def ledger_state(ledger: Any) -> Dict[str, Any]:
    return {"cash": ledger.cash, "side": ledger.side, "layers": [asdict(l) for l in ledger.layers],
            "open": dict(ledger._open), "skipped_layers": ledger.skipped_layers}


def restore_ledger(ledger: Any, state: Mapping[str, Any]) -> None:
    ledger.cash = float(state["cash"])
    ledger.side = state["side"]
    ledger.layers = [LedgerLayer(**l) for l in state["layers"]]
    ledger._open = dict(state["open"])
    ledger.skipped_layers = int(state.get("skipped_layers", 0))
    ledger.trades = []
    ledger.equity_curve = []


def read_snapshot(path: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(path.read_text()) if path.exists() else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Replay of one machine (entry x symbol) from the anchor, or from its snapshot
# ---------------------------------------------------------------------------

@dataclass
class ShadowEvent:
    key: str
    run: str
    symbol: str
    action: str
    side: str
    candle_open: str
    candle_close: str
    price: Optional[float]
    regime_own: Optional[str] = None
    regime_btc: Optional[str] = None
    books: Dict[str, bool] = field(default_factory=dict)
    reasons: List[str] = field(default_factory=list)
    notional_usdt: Optional[float] = None
    invalidation: Optional[float] = None
    carried: bool = False
    recorded_at: Optional[str] = None
    notified: Optional[bool] = None


@dataclass
class ShadowTrade:
    key: str
    run: str
    symbol: str
    side: str
    entry_time: str
    exit_time: str
    exit_reason: str
    bars_held: int
    n_layers: int
    avg_price: float
    exit_price: float
    invalidation: Optional[float]
    r_net: float
    pnl_net_usdt: float
    cost_usdt: float
    funding_usdt: float
    r_unit_usdt: Optional[float]
    equity_after: float
    cluster: str
    block: str
    regime_own: Optional[str]
    regime_btc: Optional[str]
    books: Dict[str, bool]
    reasons: List[str]
    partial_takes: int
    recorded_at: Optional[str] = None


def _snapshot_check(snap: Mapping[str, Any], *, key: str, symbol: str, params: Any, anchor_ms: int, activation_ms: int,
                    first: int, last: int, machine: SequentialMachine, frames: Mapping[str, pd.DataFrame]) -> Optional[str]:
    """None when `snap` was built on the same inputs up to its candle; else why not."""
    k = int(snap.get("bar", -1))
    if snap.get("version") != SNAPSHOT_VERSION or snap.get("rule") != RULE_LABEL:
        return "version"
    if snap.get("run") != key or snap.get("symbol") != symbol:
        return "identity"
    if snap.get("params") != _params_json(params):
        return "params"
    if int(snap.get("anchor_ms", -1)) != anchor_ms or int(snap.get("activation_ms", -1)) != activation_ms:
        return "window"
    if int(snap.get("first", -1)) != first or k < first or k > last - 1:
        return "range"
    if machine.trig.open_ms is None or int(machine.trig.open_ms[k]) != int(snap.get("open_ms", -1)):
        return "open_ms"
    if snap.get("trigger_sha") != frame_prefix_sha(frames[params.trigger_tf], k + 1):
        return "trigger_sha"
    ctx = snap.get("ctx", {})
    for tf, idx in machine.ctx_idx.items():
        pos = int(idx[k])
        want = ctx.get(tf)
        if not want or int(want.get("pos", -2)) != pos or want.get("sha") != frame_prefix_sha(frames[tf], pos + 1):
            return f"ctx_sha:{tf}"
    return None


def _snapshot_build(*, key: str, symbol: str, entry: str, params: Any, anchor_ms: int, activation_ms: int, first: int, k: int,
                    machine: SequentialMachine, ledger: Any, frames: Mapping[str, pd.DataFrame],
                    entries_before: Iterable[int]) -> Dict[str, Any]:
    return {
        "version": SNAPSHOT_VERSION, "rule": RULE_LABEL, "run": key, "symbol": symbol, "entry": entry,
        "params": _params_json(params), "anchor_ms": anchor_ms, "activation_ms": activation_ms, "first": first,
        "bar": k, "open_ms": int(machine.trig.open_ms[k]), "candle_open": iso(int(machine.trig.open_ms[k])),
        "trigger_sha": frame_prefix_sha(frames[params.trigger_tf], k + 1),
        "ctx": {tf: {"pos": int(idx[k]), "sha": frame_prefix_sha(frames[tf], int(idx[k]) + 1)} for tf, idx in machine.ctx_idx.items()},
        "entries_before": sorted(int(x) for x in entries_before),
        "machine": machine_state(machine), "ledger": ledger_state(ledger),
    }


def replay(entry: str, symbol: str, frames: Mapping[str, pd.DataFrame], *, anchor_ms: int, activation_ms: int,
           own: Optional[RegimeSeries], btc: Optional[RegimeSeries], warmup: int = WARMUP_BARS,
           shared: Optional[SequentialMachine] = None, snapshot: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """Drive the machine + ledger over `frames` (enriched) from the anchor — or from `snapshot`
    when it was built on the same candles — and return the events / trades at or after the
    activation, the open book at the end, the last candle and the snapshot to save
    (state at the candle before the last one; None when there is no such candle)."""
    params = params_for(entry)
    key = run_key(entry)
    tf = params.trigger_tf
    trig = frames[tf]
    first = max(int(warmup), int(trig.index.searchsorted(pd.Timestamp(anchor_ms, unit="ms", tz="UTC"))))
    last = len(trig) - 1
    machine = SequentialMachine(params, frames, equity=params.equity_usdt, derived_from=shared)
    ledger = ledger_for(params, split=datetime.fromtimestamp(anchor_ms / 1000.0, tz=timezone.utc), symbol=symbol)
    driver = SequentialDriver(machine, ledger, trig, timeframe=tf)
    entries_before: set = set()
    start = first
    resumed: Optional[str] = None
    if snapshot is not None:
        why = _snapshot_check(snapshot, key=key, symbol=symbol, params=params, anchor_ms=anchor_ms, activation_ms=activation_ms,
                              first=first, last=last, machine=machine, frames=frames)
        if why is None:
            restore_machine(machine, snapshot["machine"])
            restore_ledger(ledger, snapshot["ledger"])
            entries_before = {int(x) for x in snapshot.get("entries_before", [])}
            start = int(snapshot["bar"]) + 1
            resumed = "ok"
        else:
            resumed = f"rebuilt:{why}"
    decisions: List[Any] = []
    liquidations = 0
    new_snapshot: Optional[Dict[str, Any]] = None
    for i in range(start, last + 1):
        if i == last and i - 1 >= first and machine.trig.open_ms is not None:  # state is at the candle before the last one
            new_snapshot = _snapshot_build(key=key, symbol=symbol, entry=entry, params=params, anchor_ms=anchor_ms,
                                           activation_ms=activation_ms, first=first, k=i - 1, machine=machine, ledger=ledger,
                                           frames=frames, entries_before=entries_before)
        d, liq = driver.bar(i)
        liquidations += int(liq)
        decisions.append(d)
        if d.action == "enter" and d.timestamp is not None and decision_ms(int(d.timestamp), tf) < activation_ms:
            entries_before.add(int(d.timestamp))

    events: List[ShadowEvent] = []
    for d in decisions:
        if d.action not in RECORDED_ACTIONS or d.timestamp is None:
            continue
        open_ms = int(d.timestamp)
        close_ms = decision_ms(open_ms, tf)
        if close_ms < activation_ms:
            continue
        labels = label_signal(open_ms, tf, own, btc) if d.action == "enter" else {}
        values = (d.context or {}).get("values", {}) if isinstance(d.context, dict) else {}
        ev = ShadowEvent(
            key=f"{key}|{symbol}|{d.action}|{iso(open_ms)}", run=key, symbol=symbol, action=d.action, side=d.side,
            candle_open=iso(open_ms), candle_close=iso(close_ms), price=values.get("close"),
            regime_own=labels.get("regime_own"), regime_btc=labels.get("regime_btc"),
            books=book_of(d.side, labels) if d.action == "enter" else {},
            reasons=[str(r) for r in d.reasons], notional_usdt=getattr(d, "notional", None),
            invalidation=getattr(d, "invalidation_price", None),
        )
        if d.action == "exit":
            ev.carried = _entry_open_of(machine, d) in entries_before
        events.append(ev)
    trades: List[ShadowTrade] = []
    for t in ledger.trades:
        entry_open_ms = ms_of(t.entry_time)
        if t.exit_reason == "end_of_data" or decision_ms(entry_open_ms, tf) < activation_ms:
            continue
        labels = label_signal(entry_open_ms, tf, own, btc)
        trades.append(ShadowTrade(
            key=f"{key}|{symbol}|{t.entry_time}", run=key, symbol=symbol, side=t.side, entry_time=t.entry_time,
            exit_time=t.exit_time, exit_reason=t.exit_reason, bars_held=t.bars_held, n_layers=t.n_layers,
            avg_price=t.avg_price, exit_price=t.exit_price, invalidation=t.invalidation, r_net=float(t.r_net),
            pnl_net_usdt=float(t.pnl_net_usdt), cost_usdt=float(t.cost_usdt), funding_usdt=float(t.funding_usdt),
            r_unit_usdt=t.r_unit_usdt, equity_after=float(t.equity_after), cluster=t.cluster, block=t.block,
            regime_own=labels["regime_own"], regime_btc=labels["regime_btc"], books=book_of(t.side, labels),
            reasons=list(t.reasons), partial_takes=len(t.partial_takes),
        ))
    open_at_end = driver.open_book() if last >= first else None
    if open_at_end is not None:
        open_at_end = {k: v for k, v in open_at_end.items() if k != "layers"}
        open_at_end["entry_time"] = ledger._open["time"]
    return {"run": key, "symbol": symbol, "events": events, "trades": trades, "open": open_at_end,
            "last_candle": trig.index[-1].isoformat(), "liquidations": liquidations, "equity": round(ledger.cash, 2),
            "machine": machine, "snapshot": new_snapshot, "resumed": resumed, "bars": max(0, last + 1 - start)}


def _entry_open_of(machine: SequentialMachine, exit_decision: Any) -> Optional[int]:
    """Open ms of the entry candle of the position closed by `exit_decision` (from bars_held)."""
    ctx = exit_decision.context if isinstance(exit_decision.context, dict) else {}
    held = ctx.get("bars_held")
    if held is None or exit_decision.timestamp is None:
        return None
    return int(exit_decision.timestamp) - int(held) * TIMEFRAME_MS[machine.p.trigger_tf]


# ---------------------------------------------------------------------------
# JSONL state (append-only, deduplicated by key)
# ---------------------------------------------------------------------------

def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def append_new(path: Path, items: Iterable[Any], existing_keys: set, stamp: str) -> List[Dict[str, Any]]:
    """Append the items whose `key` is not in `existing_keys`; returns what was appended."""
    added: List[Dict[str, Any]] = []
    with path.open("a") as fh:
        for it in items:
            d = asdict(it) if not isinstance(it, dict) else dict(it)
            if d["key"] in existing_keys:
                continue
            d["recorded_at"] = stamp
            fh.write(json.dumps(d, default=str) + "\n")
            existing_keys.add(d["key"])
            added.append(d)
    return added


# ---------------------------------------------------------------------------
# ntfy (one line per entry / exit; the topic is never printed)
# ---------------------------------------------------------------------------

def ntfy_line(ev: Mapping[str, Any], trade: Optional[Mapping[str, Any]] = None) -> str:
    entry = str(ev["run"]).split(":")[1]
    side = str(ev["side"]).upper()
    reg = f"reg own={ev.get('regime_own') or '?'} btc={ev.get('regime_btc') or '?'}"
    when = str(ev["candle_close"])[:16].replace("+00", "") + "Z"
    px = f"{ev['price']:.6g}" if ev.get("price") is not None else "?"
    if ev["action"] == "enter":
        books = ",".join(b for b in ("long_only", "short_only", "regime_own", "regime_btc") if ev.get("books", {}).get(b))
        inv = f" inv {ev['invalidation']:.6g}" if ev.get("invalidation") is not None else ""
        return f"{ROUND} ENTER {side} {ev['symbol']} {entry} 1h@{when} px {px}{inv} {reg} books={books}"
    tag = " carried" if ev.get("carried") else ""
    reason = next((r for r in ev.get("reasons", []) if str(r).startswith("exit_")), "exit")
    r = f" {trade['r_net']:+.2f}R {trade['pnl_net_usdt']:+.2f} USDT" if trade else ""
    if trade:
        reg = f"reg own={trade.get('regime_own') or '?'} btc={trade.get('regime_btc') or '?'}"
    return f"{ROUND} EXIT {side} {ev['symbol']} {entry} 1h@{when} px {px}{r} ({reason}){tag} {reg}"


def ntfy_send(line: str, *, base: Optional[str] = None, topic: Optional[str] = None, timeout: float = 10.0,
              opener: Callable[..., Any] = urllib.request.urlopen) -> bool:
    base = (base or os.environ.get("NTFY_BASE") or "https://ntfy.sh").rstrip("/")
    topic = topic if topic is not None else os.environ.get("NTFY_TOPIC", "")
    if not topic:
        return False
    req = urllib.request.Request(f"{base}/{topic}", data=line.encode("utf-8"), method="POST",
                                 headers={"Title": "mmk shadow r8", "Tags": "chart_with_upwards_trend"})
    try:
        with opener(req, timeout=timeout) as resp:
            return 200 <= int(getattr(resp, "status", 200)) < 300
    except Exception:
        return False


# ---------------------------------------------------------------------------
# One shadow run (the one-shot)
# ---------------------------------------------------------------------------

def shadow_run(*, state_dir: Path, loaders: Mapping[str, Callable[[str], pd.DataFrame]], now_ms: int,
               dry_run: bool = False, anchor: str = ANCHOR, activation: str = ACTIVATION,
               symbols: Sequence[str] = UNIVERSE, entries: Sequence[str] = tuple(ENTRIES),
               notify: Callable[[str], bool] = ntfy_send, log: Callable[[str], None] = print,
               warmup: int = WARMUP_BARS, resume: bool = True) -> Dict[str, Any]:
    """Drive every (entry, symbol), append the new events / trades, notify the new enters / exits.
    `loaders[symbol](tf)` returns the raw CLOSED candles frame up to the last closed 1h candle.
    `resume=False` ignores the saved machine snapshots (full replay from the anchor); they are
    rebuilt either way. A dry run reads the caches and writes nothing."""
    t0 = time.perf_counter()
    anchor_ms, activation_ms = ms_of(anchor), ms_of(activation)
    stamp = iso(now_ms)
    state_dir = Path(state_dir)
    cache_dir = state_dir / CACHE_DIR
    events_path, trades_path, state_path = state_dir / EVENTS_FILE, state_dir / TRADES_FILE, state_dir / STATE_FILE
    if not dry_run:
        state_dir.mkdir(parents=True, exist_ok=True)
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    event_keys = {e["key"] for e in read_jsonl(events_path)}
    trade_keys = {t["key"] for t in read_jsonl(trades_path)}

    raw: Dict[str, Dict[str, pd.DataFrame]] = {}
    errors: Dict[str, str] = {}
    for sym in symbols:
        try:
            raw[sym] = {tf: loaders[sym](tf) for tf in ("1h", "4h", "1d")}
        except Exception as exc:  # one asset failing must not stop the others
            errors[sym] = f"{type(exc).__name__}: {exc}"
    t_load = time.perf_counter()

    frames: Dict[str, Dict[str, pd.DataFrame]] = {}
    tf_status: Dict[str, Dict[str, str]] = {}
    base_params = params_for(entries[0]) if entries else params_for("base")
    for sym, f in raw.items():
        try:
            frames[sym], tf_status[sym] = enriched_frames(base_params, lambda tf, f=f: f[tf], symbol=sym,
                                                          cache_dir=cache_dir, write=not dry_run)
        except Exception as exc:
            errors[sym] = f"{type(exc).__name__}: {exc}"
    regimes = {sym: regime_series(f["1d"]) for sym, f in raw.items() if len(f["1d"])}
    btc = regimes.get("BTC/USDT")
    t_enrich = time.perf_counter()

    new_events: List[ShadowEvent] = []
    new_trades: List[ShadowTrade] = []
    open_positions: Dict[str, Any] = {}
    last_candle: Dict[str, str] = {}
    snapshots: List[Tuple[Path, Dict[str, Any]]] = []
    resumed = {"ok": 0, "rebuilt": 0, "bars": 0}
    for sym, f in frames.items():
        shared: Optional[SequentialMachine] = None
        for entry in entries:
            snap = read_snapshot(snapshot_path(cache_dir, entry, sym)) if resume else None
            try:
                res = replay(entry, sym, f, anchor_ms=anchor_ms, activation_ms=activation_ms, own=regimes.get(sym), btc=btc,
                             warmup=warmup, shared=shared, snapshot=snap)
            except Exception as exc:
                errors[f"{run_key(entry)}|{sym}"] = f"{type(exc).__name__}: {exc}"
                continue
            shared = res["machine"]
            new_events += [e for e in res["events"] if e.key not in event_keys]
            new_trades += [t for t in res["trades"] if t.key not in trade_keys]
            last_candle[sym] = res["last_candle"]
            if res["open"] is not None:
                open_positions[f"{res['run']}|{sym}"] = res["open"]
            if res["snapshot"] is not None:
                snapshots.append((snapshot_path(cache_dir, entry, sym), res["snapshot"]))
            resumed["ok" if res["resumed"] == "ok" else "rebuilt"] += 1
            resumed["bars"] += int(res["bars"])
            if res["resumed"] and res["resumed"] != "ok":
                log(f"[snapshot] {run_key(entry)}|{sym}: {res['resumed']} -> full replay")
    t_machines = time.perf_counter()
    new_events.sort(key=lambda e: (e.candle_close, e.run, e.symbol))
    new_trades.sort(key=lambda t: (t.exit_time, t.run, t.symbol))
    trade_by_entry = {(t.run, t.symbol, t.exit_time): t for t in new_trades}

    appended_events: List[Dict[str, Any]] = []
    appended_trades: List[Dict[str, Any]] = []
    lines: List[str] = []
    if dry_run:
        appended_events = [asdict(e) for e in new_events]
        appended_trades = [asdict(t) for t in new_trades]
    else:
        appended_trades = append_new(trades_path, new_trades, trade_keys, stamp)
        appended_events = append_new(events_path, new_events, event_keys, stamp)
    pending: List[str] = list(state.get("ntfy_pending", []))
    for ev in appended_events:
        if ev["action"] not in NOTIFIED_ACTIONS:
            continue
        t = trade_by_entry.get((ev["run"], ev["symbol"], ev["candle_open"])) if ev["action"] == "exit" else None
        lines.append(ntfy_line(ev, asdict(t) if t else None))
    sent, failed = 0, []
    if dry_run:
        for ln in lines:
            log(f"[dry-run ntfy] {ln}")
    else:
        for ln in pending + lines:
            if notify(ln):
                sent += 1
            else:
                failed.append(ln)
    if not dry_run:
        counts = state.get("counts", {"events": 0, "trades": 0, "runs": 0})
        counts = {"events": counts.get("events", 0) + len(appended_events), "trades": counts.get("trades", 0) + len(appended_trades),
                  "runs": counts.get("runs", 0) + 1}
        state_path.write_text(json.dumps({
            "round": ROUND, "rule": RULE_LABEL, "anchor": anchor, "activation": activation, "last_run": stamp,
            "last_candle": last_candle, "open_positions": open_positions, "counts": counts,
            "ntfy_pending": failed[-50:], "errors": errors,
        }, indent=2, default=str))
        if snapshots:
            cache_dir.mkdir(parents=True, exist_ok=True)
            for path, snap in snapshots:
                write_atomic(path, json.dumps({**snap, "saved_at": stamp}, default=_json_default))
    t_end = time.perf_counter()
    perf = {"load_s": round(t_load - t0, 2), "enrich_s": round(t_enrich - t_load, 2), "machines_s": round(t_machines - t_enrich, 2),
            "io_s": round(t_end - t_machines, 2), "total_s": round(t_end - t0, 2), "resumed": resumed["ok"],
            "rebuilt": resumed["rebuilt"], "bars_driven": resumed["bars"]}
    summary = {
        "round": ROUND, "run_at": stamp, "dry_run": dry_run, "anchor": anchor, "activation": activation,
        "assets_ok": len(frames), "assets_failed": errors, "last_candle": last_candle,
        "events_new": len(appended_events), "trades_new": len(appended_trades), "open_positions": open_positions,
        "ntfy_sent": sent, "ntfy_failed": len(failed), "lines": lines, "perf": perf,
    }
    ok = "ok" if not errors else f"errors={len(errors)}"
    log(f"[{ROUND}] {stamp[:16]}Z candles {len(frames)}/{len(symbols)} events +{len(appended_events)} trades +{len(appended_trades)} "
        f"open {len(open_positions)} ntfy sent {sent} failed {len(failed)} {ok}{' (dry-run)' if dry_run else ''}")
    return summary


def make_loaders(symbols: Sequence[str], *, cache_dir: Path, anchor_ms: int, end_ms: int, now_ms: int,
                 fetch: Optional[Callable[..., List[List[Any]]]] = None,
                 fallback: Optional[Callable[..., List[List[Any]]]] = None,
                 log: Callable[[str], None] = print) -> Dict[str, Callable[[str], pd.DataFrame]]:
    """Per-symbol loaders over the incremental cache (public bitget spot, no keys)."""
    if fetch is None:
        fetch, fallback = exchange_fetchers()
    cache: Dict[str, pd.DataFrame] = {}

    def loader_for(sym: str) -> Callable[[str], pd.DataFrame]:
        def load(tf: str) -> pd.DataFrame:
            k = f"{sym}@{tf}"
            if k not in cache:
                t0 = time.time()
                df, info = load_incremental(sym, tf, since_ms=warmup_since_ms(anchor_ms, tf), end_ms=end_ms,
                                            cache_dir=cache_dir, fetch=fetch, fallback=fallback, now_ms=now_ms)
                log(f"[data] {k}: {info['rows']} rows (+{info['fetched']}) last {info['last_open']} ({time.time() - t0:.1f}s)")
                cache[k] = df
            return cache[k]
        return load

    return {sym: loader_for(sym) for sym in symbols}


# ---------------------------------------------------------------------------
# Report (signals and R per book and regime)
# ---------------------------------------------------------------------------

def _stats(trades: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    rs = [float(t["r_net"]) for t in trades]
    if not rs:
        return {"n": 0}
    gains = sum(r for r in rs if r > 0)
    losses = -sum(r for r in rs if r < 0)
    return {"n": len(rs), "sum_r": round(sum(rs), 3), "exp_r": round(sum(rs) / len(rs), 3),
            "pf": round(gains / losses, 2) if losses > 0 else None, "win": round(sum(1 for r in rs if r > 0) / len(rs), 3),
            "pnl_net_usdt": round(sum(float(t["pnl_net_usdt"]) for t in trades), 2)}


def shadow_report(state_dir: Path, *, now_ms: Optional[int] = None) -> Dict[str, Any]:
    state_dir = Path(state_dir)
    events = read_jsonl(state_dir / EVENTS_FILE)
    trades = read_jsonl(state_dir / TRADES_FILE)
    state = json.loads((state_dir / STATE_FILE).read_text()) if (state_dir / STATE_FILE).exists() else {}
    enters = [e for e in events if e["action"] == "enter"]
    runs = sorted({e["run"] for e in enters} | {t["run"] for t in trades} | {run_key(e) for e in ENTRIES})
    out: Dict[str, Any] = {"state": {k: v for k, v in state.items() if k != "ntfy_pending"}, "runs": {}}
    activation_ms = ms_of(state.get("activation", ACTIVATION))
    now_ms = int(time.time() * 1000) if now_ms is None else now_ms
    out["days_elapsed"] = round(max(0.0, (now_ms - activation_ms) / 86_400_000.0), 2)
    for rk in runs:
        ev = [e for e in enters if e["run"] == rk]
        tr = [t for t in trades if t["run"] == rk]
        signals: Dict[str, Dict[str, int]] = {}
        for side in ("long", "short"):
            signals[side] = {"n": sum(1 for e in ev if e["side"] == side)}
            for ident in ("own", "btc"):
                for reg in ("up", "down"):
                    signals[side][f"{ident}_{reg}"] = sum(1 for e in ev if e["side"] == side and e.get(f"regime_{ident}") == reg)
        books = {b: _stats([t for t in tr if t.get("books", {}).get(b)]) for b in BOOKS}
        by_regime: Dict[str, Any] = {}
        for side in ("long", "short"):
            for ident in ("own", "btc"):
                for reg in ("up", "down"):
                    by_regime[f"{side}|{ident}|{reg}"] = _stats([t for t in tr if t["side"] == side and t.get(f"regime_{ident}") == reg])
        out["runs"][rk] = {"signals": signals, "books": books, "by_regime": by_regime, "closed_trades": len(tr)}
    base = out["runs"].get(run_key("base"), {}).get("signals", {})
    out["closure"] = {"signals_long_base": base.get("long", {}).get("n", 0), "signals_short_base": base.get("short", {}).get("n", 0),
                      "target_per_side": 60, "max_days": 90,
                      "closed": (base.get("long", {}).get("n", 0) >= 60 and base.get("short", {}).get("n", 0) >= 60) or out["days_elapsed"] >= 90}
    return out


def report_markdown(rep: Mapping[str, Any]) -> str:
    st = rep.get("state", {})
    md = [f"# mmk shadow {ROUND} — report", "",
          f"activation {st.get('activation', ACTIVATION)} · last run {st.get('last_run', '—')} · days elapsed {rep.get('days_elapsed')} · "
          f"runs {st.get('counts', {}).get('runs', 0)} · open positions {len(st.get('open_positions', {}))} · "
          f"closure {'YES' if rep['closure']['closed'] else 'no'} (base signals long {rep['closure']['signals_long_base']} / "
          f"short {rep['closure']['signals_short_base']}, target 60 each or 90 days)", ""]
    if st.get("errors"):
        md += [f"errors last run: {st['errors']}", ""]
    md += ["## Signals (entries) per side and regime", "", "| run | side | n | own up | own down | btc up | btc down |", "|---|---|---|---|---|---|---|"]
    for rk, r in rep["runs"].items():
        for side, s in r["signals"].items():
            md.append(f"| {rk} | {side} | {s['n']} | {s['own_up']} | {s['own_down']} | {s['btc_up']} | {s['btc_down']} |")
    md += ["", "## Closed trades per book", "", "| run | book | n | sum R | exp. R | PF | win | net USDT |", "|---|---|---|---|---|---|---|---|"]
    for rk, r in rep["runs"].items():
        for b, s in r["books"].items():
            if s["n"]:
                md.append(f"| {rk} | {b} | {s['n']} | {s['sum_r']} | {s['exp_r']} | {s['pf'] if s['pf'] is not None else '—'} | {s['win']} | {s['pnl_net_usdt']} |")
            else:
                md.append(f"| {rk} | {b} | 0 | — | — | — | — | — |")
    md += ["", "## Closed trades per side and regime", "", "| run | side | ident | regime | n | sum R | exp. R | PF | win | net USDT |", "|---|---|---|---|---|---|---|---|---|---|"]
    for rk, r in rep["runs"].items():
        for k, s in r["by_regime"].items():
            side, ident, reg = k.split("|")
            if s["n"]:
                md.append(f"| {rk} | {side} | {ident} | {reg} | {s['n']} | {s['sum_r']} | {s['exp_r']} | {s['pf'] if s['pf'] is not None else '—'} | {s['win']} | {s['pnl_net_usdt']} |")
    if st.get("open_positions"):
        md += ["", "## Open positions (paper, replayed)", "", "| machine | side | entry | avg price | layers | unrealized net USDT |", "|---|---|---|---|---|---|"]
        for k, o in st["open_positions"].items():
            md.append(f"| {k} | {o.get('side')} | {o.get('entry_time') or '—'} | {o.get('avg_price')} | {o.get('n_layers')} | {o.get('unrealized_net_usdt')} |")
    return "\n".join(md)
