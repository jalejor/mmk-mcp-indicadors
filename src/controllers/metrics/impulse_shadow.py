"""Impulsos-v2 round 8: FORWARD SHADOW runner (paper, local JSONL, ntfy), long + short.

Protocol: docs/PREREG_IMPULSOS_v2_r8_shadow.md. Every hourly run REPLAYS the frozen 2.3.0
snipper chain (`r5_params("snipper", entry_filter)`, book 5x cross) of the 3 entries x 9
assets from the fixed ANCHOR up to the last CLOSED 1h candle. The machine is causal, so a
decision never changes once made: the shadow's state is the JSONL of recorded events and
trades, deduplicated by key, which makes a repeated run a no-op. Each ENTER is labelled with
the two regime identifiers of `impulse_regime` at its trigger close.

Additive and isolated: nothing here is imported by the live API; no Mongo, no Telegram, no
exchange keys (public spot OHLCV through the same `MarketDataService` the backtests use).
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import pandas as pd

from .impulse_backtest import (
    TIMEFRAME_MS,
    WARMUP_BARS,
    bitget_history_fetcher,
    closed_only,
    drive_sequential,
    enrich_tv,
    fetch_ohlcv_forward,
    ledger_for,
    load_sequential_frames,
    rows_to_frame,
    utc,
)
from .impulse_regime import RegimeSeries, book_of, decision_ms, label_signal, regime_series
from .impulse_sequential import SequentialMachine, r5_params

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
    """Closed candles in [since_ms, end_ms): the cache is extended from its last row, never refetched."""
    path = cache_path(cache_dir, symbol, timeframe)
    cached: List[List[Any]] = []
    if path.exists():
        meta = json.loads(path.read_text())
        if int(meta.get("since_ms", 1 << 62)) <= since_ms:
            cached = [r for r in meta.get("rows", []) if int(r[0]) >= since_ms]
    cursor = int(cached[-1][0]) + TIMEFRAME_MS[timeframe] if cached else since_ms
    fetched = 0
    if cursor < end_ms:
        fresh = fetch_ohlcv_forward(fetch, symbol=symbol, timeframe=timeframe, since_ms=cursor, end_ms=end_ms, fallback=fallback)
        fetched = sum(1 for r in fresh if int(r[0]) < end_ms)
        cached = merge_rows(cached, fresh)
    df = closed_only(rows_to_frame(cached), timeframe, utc(datetime.fromtimestamp(end_ms / 1000.0, tz=timezone.utc)), now_ms=now_ms)
    rows = df[["timestamp", "open", "high", "low", "close", "volume"]].values.tolist()
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
# Replay of one machine (entry x symbol) from the anchor
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


def replay(entry: str, symbol: str, frames: Mapping[str, pd.DataFrame], *, anchor_ms: int, activation_ms: int,
           own: Optional[RegimeSeries], btc: Optional[RegimeSeries], warmup: int = WARMUP_BARS) -> Dict[str, Any]:
    """Drive the machine + ledger over `frames` (raw closed candles, enriched here) from the anchor.
    Returns the events / trades at or after the activation, the open book at the end and the last candle."""
    params = params_for(entry)
    key = run_key(entry)
    enriched, status = load_sequential_frames(params, lambda tf: frames[tf])
    trig = enriched[params.trigger_tf]
    first = max(int(warmup), int(trig.index.searchsorted(pd.Timestamp(anchor_ms, unit="ms", tz="UTC"))))
    machine = SequentialMachine(params, enriched, equity=params.equity_usdt)
    ledger = ledger_for(params, split=datetime.fromtimestamp(anchor_ms / 1000.0, tz=timezone.utc), symbol=symbol)
    run = drive_sequential(machine, ledger, trig, first=first, timeframe=params.trigger_tf)
    tf = params.trigger_tf
    entries_before: set = set()
    events: List[ShadowEvent] = []
    for d in run["decisions"]:
        if d.action not in RECORDED_ACTIONS or d.timestamp is None:
            continue
        open_ms = int(d.timestamp)
        close_ms = decision_ms(open_ms, tf)
        if d.action == "enter" and close_ms < activation_ms:
            entries_before.add(open_ms)
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
    open_at_end = run["open_at_end"]
    if open_at_end is not None:
        open_at_end = {k: v for k, v in open_at_end.items() if k != "layers"}
        open_at_end["entry_time"] = ledger.trades[-1].entry_time if ledger.trades and ledger.trades[-1].exit_reason == "end_of_data" else None
    return {"run": key, "symbol": symbol, "events": events, "trades": trades, "open": open_at_end,
            "last_candle": trig.index[-1].isoformat(), "tf_status": status, "liquidations": run["liquidations"],
            "equity": round(ledger.cash, 2)}


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
               warmup: int = WARMUP_BARS) -> Dict[str, Any]:
    """Replay every (entry, symbol), append the new events / trades, notify the new enters / exits.
    `loaders[symbol](tf)` returns the raw CLOSED candles frame up to the last closed 1h candle."""
    anchor_ms, activation_ms = ms_of(anchor), ms_of(activation)
    stamp = iso(now_ms)
    state_dir = Path(state_dir)
    events_path, trades_path, state_path = state_dir / EVENTS_FILE, state_dir / TRADES_FILE, state_dir / STATE_FILE
    if not dry_run:
        state_dir.mkdir(parents=True, exist_ok=True)
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    event_keys = {e["key"] for e in read_jsonl(events_path)}
    trade_keys = {t["key"] for t in read_jsonl(trades_path)}

    frames: Dict[str, Dict[str, pd.DataFrame]] = {}
    errors: Dict[str, str] = {}
    for sym in symbols:
        try:
            frames[sym] = {tf: loaders[sym](tf) for tf in ("1h", "4h", "1d")}
        except Exception as exc:  # one asset failing must not stop the others
            errors[sym] = f"{type(exc).__name__}: {exc}"
    regimes = {sym: regime_series(f["1d"]) for sym, f in frames.items() if len(f["1d"])}
    btc = regimes.get("BTC/USDT")

    new_events: List[ShadowEvent] = []
    new_trades: List[ShadowTrade] = []
    open_positions: Dict[str, Any] = {}
    last_candle: Dict[str, str] = {}
    for sym, f in frames.items():
        for entry in entries:
            try:
                res = replay(entry, sym, f, anchor_ms=anchor_ms, activation_ms=activation_ms, own=regimes.get(sym), btc=btc,
                             warmup=warmup)
            except Exception as exc:
                errors[f"{run_key(entry)}|{sym}"] = f"{type(exc).__name__}: {exc}"
                continue
            new_events += [e for e in res["events"] if e.key not in event_keys]
            new_trades += [t for t in res["trades"] if t.key not in trade_keys]
            last_candle[sym] = res["last_candle"]
            if res["open"] is not None:
                open_positions[f"{res['run']}|{sym}"] = res["open"]
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
    summary = {
        "round": ROUND, "run_at": stamp, "dry_run": dry_run, "anchor": anchor, "activation": activation,
        "assets_ok": len(frames), "assets_failed": errors, "last_candle": last_candle,
        "events_new": len(appended_events), "trades_new": len(appended_trades), "open_positions": open_positions,
        "ntfy_sent": sent, "ntfy_failed": len(failed), "lines": lines,
    }
    if not dry_run:
        counts = state.get("counts", {"events": 0, "trades": 0, "runs": 0})
        counts = {"events": counts.get("events", 0) + len(appended_events), "trades": counts.get("trades", 0) + len(appended_trades),
                  "runs": counts.get("runs", 0) + 1}
        state_path.write_text(json.dumps({
            "round": ROUND, "rule": RULE_LABEL, "anchor": anchor, "activation": activation, "last_run": stamp,
            "last_candle": last_candle, "open_positions": open_positions, "counts": counts,
            "ntfy_pending": failed[-50:], "errors": errors,
        }, indent=2, default=str))
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
