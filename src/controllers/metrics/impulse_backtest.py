"""Impulsos-v2 backtest harness: legacy engine vs the new impulse engine.

Pre-registered in `docs/PREREG_IMPULSOS_v2.md`. A NEW module on purpose (same
reasoning as `setup_backtest_service` / `fep_cont_backtest`): it touches no
live rule path. Both engines are scored with ONE trade/cost model so the
comparison is fair:

* entry at the close of the signal bar;
* stop = ``atr_mult_stop x ATR14`` of the entry bar, checked intrabar from the
  next bar on, stop-first (worst case);
* costs (known-errors E16): ``(fee + slip) * (entry + exit) / stop_distance``
  R, 0.10% + 0.05% per side — the arithmetic of
  ``SetupBacktestService._simulate_outcome``;
* R = distance to the stop.

The legacy engine (`BacktestService`, `/v1/backtest`) keeps its own exit rule
(3R target or stop) — that IS the legacy engine. The new engine exits on its
own ``exit`` decision or the stop. Statistics reuse `fep_cont_backtest`
(`metrics_block`, `cluster_bootstrap_ci`, `ohlcv_sha256`).

Data: `load_ohlcv` paginates forward with ``limit=200`` (E13), keeps closed
candles only and caches per (exchange, symbol, timeframe) as JSON.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import pandas as pd

from .fep_cont_backtest import cluster_bootstrap_ci, metrics_block, ohlcv_sha256
from .market_data_service import _month_candle_close_ms
from .setup_backtest_service import DEFAULT_FEE_RATE_PER_SIDE, DEFAULT_SLIPPAGE_PER_SIDE

BITGET_PAGE_LIMIT = 200  # E13: bitget honours `since` only with limit <= 200
WARMUP_BARS = 300  # BBWP (13/256) + Konkorde need ~270 bars
LEGACY_WARMUP_BARS = 250  # what /v1/backtest itself fetches (BacktestService default)
RISK_PER_TRADE_PCT = 1.5  # legacy default; used only for the %-drawdown reading
FUNDING_RATE_PER_8H = 0.0001  # spec §g: perp funding, charged regardless of sign
# Spec §f/§g: shorts are perps; longs are leveraged on these profiles (ancient
# longs = spot 1x, legacy longs = spot, so no funding there).
LEVERAGED_LONG_PROFILES = frozenset({"scalper", "snipper", "pro"})
BOOTSTRAP_SEED = 42  # spec §g (10 000 resamples)
BLOCK_IS = "in_sample"
BLOCK_OOS = "out_of_sample"

TIMEFRAME_MS: Dict[str, int] = {
    "15m": 15 * 60_000,
    "30m": 30 * 60_000,
    "1h": 60 * 60_000,
    "4h": 4 * 60 * 60_000,
    "1d": 24 * 60 * 60_000,
    "1w": 7 * 24 * 60 * 60_000,
    "1M": 31 * 24 * 60 * 60_000,  # upper bound; month closes use the calendar
}

_LONG_ALIASES = {"long", "buy", "up", "bull", "bullish"}
_SHORT_ALIASES = {"short", "sell", "down", "bear", "bearish"}


# ----------------------------------------------------------------------
# Data
# ----------------------------------------------------------------------

def utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def candle_close_ms(open_ms: int, timeframe: str) -> int:
    if timeframe == "1M":
        return _month_candle_close_ms(open_ms)
    return open_ms + TIMEFRAME_MS[timeframe]


def warmup_since(start: datetime, timeframe: str, bars: int = WARMUP_BARS) -> datetime:
    return utc(start) - timedelta(milliseconds=TIMEFRAME_MS[timeframe] * bars)


def rows_to_frame(rows: Iterable[Sequence[Any]]) -> pd.DataFrame:
    df = pd.DataFrame(list(rows), columns=["timestamp", "open", "high", "low", "close", "volume"])
    if df.empty:
        return df
    df["timestamp"] = df["timestamp"].astype("int64")
    # Fixed dtypes so the sha256 is identical before and after the JSON cache.
    df[["open", "high", "low", "close", "volume"]] = df[["open", "high", "low", "close", "volume"]].astype(float)
    df = df.drop_duplicates(subset="timestamp").sort_values("timestamp")
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    return df.set_index("datetime")


def closed_only(
    df: pd.DataFrame, timeframe: str, end: datetime, now_ms: Optional[float] = None
) -> pd.DataFrame:
    """Keep candles that opened before `end` and had closed by `now`."""
    if df.empty:
        return df
    now_ms = time.time() * 1000.0 if now_ms is None else now_ms
    end_ms = int(utc(end).timestamp() * 1000)
    closes = df["timestamp"].map(lambda ts: candle_close_ms(int(ts), timeframe))
    return df[(df["timestamp"] < end_ms) & (closes <= now_ms)]


def fetch_ohlcv_forward(
    fetch: Callable[..., List[List[Any]]],
    *,
    symbol: str,
    timeframe: str,
    since_ms: int,
    end_ms: int,
    limit: int = BITGET_PAGE_LIMIT,
    max_pages: int = 5000,
    fallback: Optional[Callable[..., List[List[Any]]]] = None,
) -> List[List[Any]]:
    """Forward pagination that survives empty pages until `end_ms`.

    An empty page (pre-listing range, or bitget's hand-over between its
    history and recent endpoints — seen live 2026-11-01 on 1h/15m, where
    stopping at the first empty page truncated months) jumps one page ahead
    instead of stopping. Remaining holes are reported by `count_gaps`.
    """
    rows: List[List[Any]] = []
    cursor = since_ms
    page_span = TIMEFRAME_MS[timeframe] * limit
    for _ in range(max_pages):
        if cursor >= end_ms:
            break
        batch = fetch(symbol=symbol, timeframe=timeframe, since=cursor, limit=limit)
        batch = [r for r in (batch or []) if int(r[0]) >= cursor]
        step = TIMEFRAME_MS[timeframe]
        if fallback is not None and (not batch or int(batch[0][0]) > cursor + step):
            # Empty page, or a hole at its head: patch from the raw endpoint.
            head = int(batch[0][0]) if batch else None
            extra = [r for r in fallback(symbol=symbol, timeframe=timeframe, since=cursor, limit=limit)
                     if int(r[0]) >= cursor and (head is None or int(r[0]) < head)]
            batch = sorted(extra + batch, key=lambda r: int(r[0]))
        if not batch:
            cursor += page_span
            continue
        rows.extend(batch)
        nxt = int(batch[-1][0]) + 1
        if nxt <= cursor:
            break
        cursor = nxt
    return rows


def bitget_history_fetcher(exchange: Any) -> Callable[..., List[List[Any]]]:
    """Raw bitget v2 `history-candles` page: `limit` rows ending at since+limit*tf.

    ccxt 4.2.97 returns EMPTY pages for a band of ~25 days just before the
    recent window on 1h/15m (seen live 2026-11-01: 1h 2026-08-13 -> 09-07,
    600 candles); the raw endpoint called with `endTime` serves them.
    """

    def fetch(*, symbol: str, timeframe: str, since: int, limit: int) -> List[List[Any]]:
        exchange.load_markets()
        granularity = exchange.options["timeframes"]["spot"].get(timeframe, timeframe)
        resp = exchange.publicSpotGetV2SpotMarketHistoryCandles({
            "symbol": exchange.market(symbol)["id"],
            "granularity": granularity,
            "endTime": str(int(since) + limit * TIMEFRAME_MS[timeframe]),
            "limit": str(limit),
        })
        rows = [[int(r[0]), *map(float, r[1:6])] for r in resp.get("data") or []]
        return sorted(rows, key=lambda r: r[0])

    return fetch


def count_gaps(df: pd.DataFrame, timeframe: str) -> int:
    """Missing candles between consecutive rows (fixed-duration TFs only)."""
    if timeframe == "1M" or len(df) < 2:
        return 0
    step = TIMEFRAME_MS[timeframe]
    diffs = df["timestamp"].diff().dropna().astype("int64")
    return int(((diffs // step) - 1).clip(lower=0).sum())


@dataclass
class FrameInfo:
    exchange: str
    symbol: str
    timeframe: str
    rows: int
    first_open: str
    last_open: str
    sha256: str
    source: str  # cache | exchange
    gaps: int = 0


def _cache_path(cache_dir: str, exchange: str, symbol: str, timeframe: str) -> Path:
    safe = symbol.replace("/", "-").replace(":", "-")
    return Path(cache_dir) / f"{exchange}_{safe}_{timeframe}.json"


def load_ohlcv(
    symbol: str,
    timeframe: str,
    start: datetime,
    end: datetime,
    exchange: str = "bitget",
    cache_dir: str = "/data/ohlcv",
    warmup_bars: int = WARMUP_BARS,
    fetch: Optional[Callable[..., List[List[Any]]]] = None,
) -> tuple[pd.DataFrame, FrameInfo]:
    """Closed OHLCV for [start - warmup, end), cached per (exchange, symbol, tf)."""
    since_ms = int(warmup_since(start, timeframe, warmup_bars).timestamp() * 1000)
    end_ms = int(utc(end).timestamp() * 1000)
    path = _cache_path(cache_dir, exchange, symbol, timeframe)

    source = "cache"
    raw: Optional[pd.DataFrame] = None
    if path.exists():
        meta = json.loads(path.read_text())
        reaches_end = bool(meta.get("rows")) and (
            int(meta["rows"][-1][0]) + 2 * TIMEFRAME_MS[timeframe] >= min(end_ms, time.time() * 1000)
        )
        if meta.get("since_ms", 1 << 62) <= since_ms and meta.get("end_ms", 0) >= end_ms and reaches_end:
            raw = rows_to_frame(meta["rows"])
    if raw is None:
        source = "exchange"
        fallback = None
        if fetch is None:
            from .market_data_service import MarketDataService

            ex = MarketDataService(exchange_name=exchange).exchange
            fetch = ex.fetch_ohlcv
            if exchange == "bitget" and timeframe != "1M":
                fallback = bitget_history_fetcher(ex)
        rows = fetch_ohlcv_forward(
            fetch, symbol=symbol, timeframe=timeframe, since_ms=since_ms, end_ms=end_ms,
            fallback=fallback,
        )
        raw = closed_only(rows_to_frame(rows), timeframe, end)
        if raw.empty:
            raise ValueError(f"No closed OHLCV for {exchange} {symbol} {timeframe}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "exchange": exchange,
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "since_ms": since_ms,
                    "end_ms": end_ms,
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "sha256": ohlcv_sha256(raw),
                    "rows": raw[["timestamp", "open", "high", "low", "close", "volume"]].values.tolist(),
                }
            )
        )

    df = raw[(raw["timestamp"] >= since_ms) & (raw["timestamp"] < end_ms)]
    info = FrameInfo(
        exchange=exchange,
        symbol=symbol,
        timeframe=timeframe,
        rows=len(df),
        first_open=df.index[0].isoformat() if len(df) else "",
        last_open=df.index[-1].isoformat() if len(df) else "",
        sha256=ohlcv_sha256(df) if len(df) else "",
        source=source,
        gaps=count_gaps(df, timeframe),
    )
    return df, info


# ----------------------------------------------------------------------
# Trade model (shared by both engines)
# ----------------------------------------------------------------------

@dataclass
class SimTrade:
    """One resolved trade; duck-types the fields `metrics_block` reads."""

    engine: str
    profile: str
    symbol: str
    timeframe: str
    side: str
    entry_time: str
    entry_price: float
    stop_price: float
    exit_time: Optional[str]
    exit_price: float
    exit_reason: str  # stop | target | signal_exit | end_of_data
    bars_held: int
    r_gross: float
    cost_r: float
    funding_r: float
    r_net: float
    block: str
    cluster: str
    confidence: Optional[float] = None
    reasons: List[str] = field(default_factory=list)


def cost_in_r(entry: float, exit_price: float, stop_distance: float,
              fee: float = DEFAULT_FEE_RATE_PER_SIDE,
              slip: float = DEFAULT_SLIPPAGE_PER_SIDE) -> float:
    return (fee + slip) * (entry + exit_price) / stop_distance


def funding_in_r(entry: float, stop_distance: float, held: timedelta,
                 rate_per_8h: float = FUNDING_RATE_PER_8H) -> float:
    """Spec §g: 0.01% of notional per 8h held, always charged (conservative)."""
    return rate_per_8h * (held.total_seconds() / (8 * 3600)) * entry / stop_distance


def make_trade(
    *, engine: str, profile: str, symbol: str, timeframe: str, side: str,
    entry_time: datetime, entry_price: float, stop_distance: float,
    exit_time: Optional[datetime], exit_price: float, exit_reason: str,
    bars_held: int, split: datetime, reasons: Optional[List[str]] = None,
    fee: float = DEFAULT_FEE_RATE_PER_SIDE, slip: float = DEFAULT_SLIPPAGE_PER_SIDE,
    charge_funding: bool = False, confidence: Optional[float] = None,
) -> SimTrade:
    gross = (exit_price - entry_price) if side == "long" else (entry_price - exit_price)
    r_gross = gross / stop_distance
    cost_r = cost_in_r(entry_price, exit_price, stop_distance, fee, slip)
    entry_time = utc(entry_time)
    funding_r = 0.0
    if charge_funding and exit_time is not None:
        funding_r = funding_in_r(entry_price, stop_distance, utc(exit_time) - entry_time)
    stop_price = entry_price - stop_distance if side == "long" else entry_price + stop_distance
    return SimTrade(
        engine=engine, profile=profile, symbol=symbol, timeframe=timeframe, side=side,
        entry_time=entry_time.isoformat(), entry_price=round(entry_price, 8),
        stop_price=round(stop_price, 8),
        exit_time=utc(exit_time).isoformat() if exit_time else None,
        exit_price=round(exit_price, 8), exit_reason=exit_reason, bars_held=bars_held,
        r_gross=round(r_gross, 6), cost_r=round(cost_r, 6), funding_r=round(funding_r, 6),
        r_net=round(r_gross - cost_r - funding_r, 6),
        block=BLOCK_IS if entry_time < utc(split) else BLOCK_OOS,
        cluster=f"{symbol}|{entry_time:%Y-%m}", confidence=confidence,
        reasons=list(reasons or []),
    )


def stop_fill(side: str, stop: float, bar_open: float) -> float:
    """Spec §g: a stop fills at the stop or at a worse (gapped) open."""
    return min(stop, bar_open) if side == "long" else max(stop, bar_open)


def charges_funding(profile: str, side: str) -> bool:
    """Shorts are perps (always funded); longs only on leveraged profiles."""
    return side == "short" or profile in LEVERAGED_LONG_PROFILES


def normalise_side(value: Any) -> Optional[str]:
    if value is None:
        return None
    v = str(getattr(value, "value", value)).lower()
    if v in _LONG_ALIASES:
        return "long"
    if v in _SHORT_ALIASES:
        return "short"
    return None


def _field(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _bar_index_for(
    df: pd.DataFrame, ts: Any, timeframe: str, timestamp_is_close: bool = False
) -> Optional[int]:
    """Map a decision timestamp (candle open by default, as the frame index) to a bar."""
    if ts is None:
        return None
    if isinstance(ts, (int, float)):
        stamp = pd.Timestamp(int(ts), unit="ms", tz="UTC")
    else:
        stamp = pd.Timestamp(ts)
        stamp = stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")
    if timestamp_is_close:
        stamp = stamp - pd.Timedelta(milliseconds=TIMEFRAME_MS[timeframe])
    if stamp in df.index:
        return int(df.index.get_loc(stamp))
    return None


def simulate_decisions(
    df: pd.DataFrame,
    decisions: Sequence[Any],
    *,
    direction: str,
    atr_mult_stop: float,
    split: datetime,
    start: datetime,
    end: datetime,
    engine: str = "new",
    profile: str = "",
    symbol: str = "",
    timeframe: str = "1d",
    fee: float = DEFAULT_FEE_RATE_PER_SIDE,
    slip: float = DEFAULT_SLIPPAGE_PER_SIDE,
    timestamp_is_close: bool = False,
    charge_funding: Optional[bool] = None,
    time_stop_bars: Optional[int] = None,
) -> List[SimTrade]:
    """Turn per-bar decisions into trades for ONE direction (1 position at a time).

    * `enter` with side == direction while flat -> open at that bar's close;
      stop = atr_mult_stop x atr14 of that bar. Entries only in [start, end).
    * From the next bar on: stop first (intrabar, worst case; fills at the
      stop or a worse gapped open); then an `exit` decision (side ==
      direction, flat or none) or an `enter` of the opposite side closes at
      that bar's close; then the optional time stop. No same-bar reversal.
    * Still open at the last bar -> `end_of_data` at the last close.
    * Funding (spec §g) defaults to `charges_funding(profile, direction)`.
    """
    if "atr14" not in df:
        raise ValueError("trigger frame needs an `atr14` column (IndicatorsService.calculate_all)")
    if charge_funding is None:
        charge_funding = charges_funding(profile, direction)
    by_bar: Dict[int, Any] = {}
    for d in decisions:
        i = _bar_index_for(df, _field(d, "timestamp"), timeframe, timestamp_is_close)
        if i is not None:
            by_bar[i] = d

    start_ts, end_ts = pd.Timestamp(utc(start)), pd.Timestamp(utc(end))
    opens, highs = df["open"].to_numpy(float), df["high"].to_numpy(float)
    lows, closes = df["low"].to_numpy(float), df["close"].to_numpy(float)
    atrs = df["atr14"].to_numpy(float)
    trades: List[SimTrade] = []
    pos: Optional[Dict[str, Any]] = None
    last = len(df) - 1

    def close(i: int, price: float, reason: str) -> None:
        trades.append(make_trade(
            engine=engine, profile=profile, symbol=symbol, timeframe=timeframe, side=direction,
            entry_time=df.index[pos["i"]].to_pydatetime(), entry_price=float(pos["entry"]),
            stop_distance=float(pos["dist"]), exit_time=df.index[i].to_pydatetime(),
            exit_price=float(price), exit_reason=reason, bars_held=i - pos["i"], split=split,
            reasons=pos["reasons"], fee=fee, slip=slip, charge_funding=bool(charge_funding),
            confidence=pos["confidence"],
        ))

    for i in range(len(df)):
        dec = by_bar.get(i)
        action = str(_field(dec, "action", "") or "").lower() if dec is not None else ""
        side = normalise_side(_field(dec, "side")) if dec is not None else None

        if pos is not None and i > pos["i"]:
            stop_hit = lows[i] <= pos["stop"] if direction == "long" else highs[i] >= pos["stop"]
            exit_now = (action == "exit" and side in (None, direction)) or (
                action == "enter" and side is not None and side != direction
            )
            timed_out = bool(time_stop_bars) and i - pos["i"] >= int(time_stop_bars)
            if stop_hit:
                close(i, stop_fill(direction, pos["stop"], opens[i]), "stop")
            elif exit_now:
                close(i, closes[i], "signal_exit")
            elif timed_out:
                close(i, closes[i], "time_stop")
            if stop_hit or exit_now or timed_out:
                pos = None
                continue  # no same-bar re-entry

        if pos is None and action == "enter" and side == direction and i < last:
            if not (start_ts <= df.index[i] < end_ts):
                continue
            atr = atrs[i]
            if not (atr > 0):
                continue
            dist = atr * atr_mult_stop
            stop = closes[i] - dist if direction == "long" else closes[i] + dist
            conf = _field(dec, "confidence")
            pos = {"i": i, "entry": closes[i], "dist": dist, "stop": stop,
                   "reasons": list(_field(dec, "reasons", []) or []),
                   "confidence": float(conf) if conf is not None else None}

    if pos is not None:
        close(last, closes[last], "end_of_data")
    return trades


# ----------------------------------------------------------------------
# Legacy engine (BacktestService over RulesService) with injected data
# ----------------------------------------------------------------------

def run_legacy(
    df: pd.DataFrame,
    *,
    symbol: str,
    timeframe: str,
    start: datetime,
    end: datetime,
    split: datetime,
    side: str,
    risk_profile: str = "medium",
    atr_stop_multiplier: Optional[float] = None,
    fee: float = DEFAULT_FEE_RATE_PER_SIDE,
    slip: float = DEFAULT_SLIPPAGE_PER_SIDE,
) -> List[SimTrade]:
    """Run `/v1/backtest`'s engine unmodified on a cached frame, one side.

    `atr_stop_multiplier` uses the engine's own override (target stays 3R):
    the "legacy at the profile's stop" reading of a cell.

    `side="short"` is the legacy engine's NATIVE short path (`signal == "exit"`
    opens a short; the route default is `side="both"`). The frame is trimmed
    to the engine's own warm-up (250 bars) so it sees what prod would fetch.
    Net R is recomputed from each trade with the shared execution model (the
    engine itself charges no fees): costs, stop fill at a worse gapped open,
    funding on shorts (perp). Legacy longs are spot -> no funding.
    """
    from .backtest_service import BacktestService

    start_ts = pd.Timestamp(utc(start))
    first = max(0, int(df.index.searchsorted(start_ts)) - LEGACY_WARMUP_BARS)
    frame = df.iloc[first:]

    svc = BacktestService(
        symbol=symbol, timeframe=timeframe, exchange="bitget", start=utc(start), end=utc(end),
        risk_profile=risk_profile, side=side, warmup_bars=LEGACY_WARMUP_BARS,  # type: ignore[arg-type]
        atr_stop_multiplier=atr_stop_multiplier,
    )
    label = f"legacy-{risk_profile}" + (f"-stop{atr_stop_multiplier}" if atr_stop_multiplier else "")
    svc._load_history = lambda: frame  # type: ignore[method-assign]  # inject, never fetch
    result = svc.run()

    trades: List[SimTrade] = []
    for t in result["trades"]:
        entry_time = pd.Timestamp(t["entry_time"]).to_pydatetime()
        if not (utc(start) <= entry_time < utc(end)):
            continue
        dist = abs(t["entry_price"] - t["stop_price"])
        exit_time = pd.Timestamp(t["exit_time"]).to_pydatetime() if t["exit_time"] else None
        i_entry = int(frame.index.get_loc(pd.Timestamp(t["entry_time"])))
        i_exit = int(frame.index.get_loc(pd.Timestamp(t["exit_time"]))) if t["exit_time"] else i_entry
        exit_price = float(t["exit_price"])
        if t["exit_reason"] == "stop":
            exit_price = stop_fill(t["side"], float(t["stop_price"]), float(frame["open"].iloc[i_exit]))
        trades.append(
            make_trade(
                engine="legacy", profile=label, symbol=symbol,
                timeframe=timeframe, side=t["side"], entry_time=entry_time,
                entry_price=float(t["entry_price"]), stop_distance=float(dist),
                exit_time=exit_time, exit_price=exit_price,
                exit_reason=t["exit_reason"], bars_held=i_exit - i_entry, split=split,
                reasons=t.get("reasons_at_entry") or [], fee=fee, slip=slip,
                charge_funding=t["side"] == "short",
            )
        )
    return trades


# ----------------------------------------------------------------------
# New engine (lazy import: --engine old must run without it)
# ----------------------------------------------------------------------

def _load_new_engine():
    try:
        from . import impulse_service, trade_profiles  # noqa: F401
    except ImportError as exc:  # pragma: no cover - depends on the other worker
        raise RuntimeError(
            "New impulse engine not available: controllers.metrics.impulse_service / "
            f"trade_profiles could not be imported ({exc}). Run --engine old, or wait "
            "for impulse_service.py to land."
        ) from exc
    return impulse_service, trade_profiles


def profile_timeframes(profile_obj: Any) -> Dict[str, Any]:
    """Resolve trigger/confirm/context timeframes from a TRADE_PROFILES entry."""

    def pick(*names: str) -> Any:
        for n in names:
            v = _field(profile_obj, n)
            if v:
                return v
        return None

    trigger = pick("trigger_tf", "trigger_timeframe", "trigger")
    confirm = pick("confirm_tf", "confirm_timeframe", "confirm")
    context = pick("context_tfs", "context_tf", "context_timeframes", "context")
    if not trigger:
        raise RuntimeError(f"cannot read the trigger timeframe from profile {profile_obj!r}")
    if isinstance(context, str):
        context = [context]
    return {"trigger": trigger, "confirm": confirm, "context": list(context or [])}


def enrich_tv(df: pd.DataFrame) -> pd.DataFrame:
    from .indicators_service import IndicatorsService

    svc = IndicatorsService(df, bbwp_definition="tv")
    svc.calculate_all()
    return svc.df


def trades_from_engine(
    df: pd.DataFrame,
    decisions: Sequence[Any],
    *,
    split: datetime,
    start: datetime,
    end: datetime,
    profile: str,
    symbol: str,
    timeframe: str,
    funded_sides: Sequence[str],
    fee: float = DEFAULT_FEE_RATE_PER_SIDE,
    slip: float = DEFAULT_SLIPPAGE_PER_SIDE,
) -> List[SimTrade]:
    """Pair the engine's own enter -> exit decisions into trades.

    `ImpulseEngine.replay` already tracks the virtual position (one book,
    long or short, no flips), the ATR stop with gap fill, the owner's exit
    rule, phase_lost and the time stop; it stamps `stop_price` on the enter
    and `exit_price` on the exit. Re-simulating that here would duplicate
    (and could silently diverge from) the engine, so the harness only adds
    the shared cost model: entry = close of the enter bar, R = |entry - stop|,
    costs E16 + funding (spec §g). An entry still open at the last bar is
    closed at the last close as `end_of_data`.
    """
    closes = df["close"].to_numpy(float)
    start_ts, end_ts = pd.Timestamp(utc(start)), pd.Timestamp(utc(end))
    trades: List[SimTrade] = []
    pos: Optional[Dict[str, Any]] = None

    def book(i: int, price: float, reason: str) -> None:
        if pos["skip"]:
            return
        trades.append(make_trade(
            engine="new", profile=profile, symbol=symbol, timeframe=timeframe, side=pos["side"],
            entry_time=df.index[pos["i"]].to_pydatetime(), entry_price=pos["entry"],
            stop_distance=pos["dist"], exit_time=df.index[i].to_pydatetime(), exit_price=price,
            exit_reason=reason, bars_held=i - pos["i"], split=split, reasons=pos["reasons"],
            fee=fee, slip=slip, charge_funding=pos["side"] in funded_sides,
            confidence=pos["confidence"],
        ))

    for d in decisions:
        i = _bar_index_for(df, _field(d, "timestamp"), timeframe)
        if i is None:
            continue
        action = str(_field(d, "action", "")).lower()
        if action == "enter" and pos is None:
            side = normalise_side(_field(d, "side"))
            stop = _field(d, "stop_price")
            entry = float(closes[i])
            if side is None or stop is None or not (abs(entry - float(stop)) > 0):
                raise ValueError(f"engine enter without side/stop at {df.index[i]}: {d!r}")
            pos = {"i": i, "side": side, "entry": entry, "dist": abs(entry - float(stop)),
                   "reasons": list(_field(d, "reasons", []) or []),
                   "confidence": _field(d, "confidence"),
                   # Engine warm-up may open before `start`; it still blocks the
                   # book (real behaviour) but is not scored.
                   "skip": not (start_ts <= df.index[i] < end_ts)}
        elif action == "exit" and pos is not None:
            price = _field(d, "exit_price")
            reasons = [r for r in (_field(d, "reasons", []) or []) if str(r).startswith("exit_")]
            book(i, float(price if price is not None else closes[i]),
                 reasons[0] if reasons else "signal_exit")
            pos = None
    if pos is not None:
        book(len(df) - 1, float(closes[-1]), "end_of_data")
    return trades


def run_new(
    *, profile: str, symbol: str, start: datetime, end: datetime, split: datetime,
    directions: Sequence[str], loader: Callable[[str], pd.DataFrame],
    fee: float = DEFAULT_FEE_RATE_PER_SIDE, slip: float = DEFAULT_SLIPPAGE_PER_SIDE,
) -> Dict[str, Any]:
    impulse_service, trade_profiles = _load_new_engine()
    tfs = profile_timeframes(trade_profiles.TRADE_PROFILES[profile])
    profile_cfg = trade_profiles.TRADE_PROFILES[profile]
    params = impulse_service.ImpulseParams.for_profile(profile)
    atr_mult = float(getattr(params, "atr_mult_stop"))
    # Time stop only if the engine/profile defines one; the harness never invents rules.
    time_stop = getattr(params, "time_stop_bars", None) or _field(profile_cfg, "time_stop_bars")

    trigger_df = enrich_tv(loader(tfs["trigger"]))
    # `ImpulseEngine.replay` takes frames keyed by timeframe; decision
    # timestamps are the open ms of the closed trigger candle.
    frames: Dict[str, pd.DataFrame] = {tfs["trigger"]: trigger_df}
    for tf in [tfs["confirm"], *tfs["context"]]:
        if tf and tf not in frames:
            frames[tf] = enrich_tv(loader(tf))

    engine = impulse_service.ImpulseEngine(params)
    # Decisions start at the window's first bar (>= 300 warm-up bars before it).
    first = max(WARMUP_BARS, int(trigger_df.index.searchsorted(pd.Timestamp(utc(start)))))
    decisions = list(engine.replay(frames, warmup=first))
    # Spec §f/§g: shorts are perps (always funded); longs only when leveraged.
    lev = float(_field(profile_cfg, "default_leverage", 1.0) or 1.0)
    funded = ("short", "long") if lev > 1.0 else ("short",)
    trades = [
        t for t in trades_from_engine(
            trigger_df, decisions, split=split, start=start, end=end, profile=profile,
            symbol=symbol, timeframe=tfs["trigger"], funded_sides=funded, fee=fee, slip=slip,
        )
        if t.side in directions
    ]
    actions: Dict[str, int] = {}
    for d in decisions:
        a = str(_field(d, "action", "")).lower()
        actions[a] = actions.get(a, 0) + 1
    return {
        "timeframes": tfs, "atr_mult_stop": atr_mult, "time_stop_bars": time_stop,
        "rule_version": _field(decisions[0], "rule_version") if decisions else None,
        "decisions": actions, "trades": trades,
        "buy_and_hold_pct": buy_and_hold_pct(trigger_df, start, end),
    }


# ----------------------------------------------------------------------
# Metrics per cell
# ----------------------------------------------------------------------

def drawdown(trades: Sequence[SimTrade], risk_pct: float = RISK_PER_TRADE_PCT) -> Dict[str, float]:
    """Max DD in R (sum of net R) and in % (fixed-fractional risk per trade)."""
    eq_r = peak_r = dd_r = 0.0
    eq = peak = 1.0
    dd_pct = 0.0
    for t in sorted(trades, key=lambda t: t.entry_time):
        eq_r += t.r_net
        peak_r = max(peak_r, eq_r)
        dd_r = max(dd_r, peak_r - eq_r)
        eq *= 1.0 + t.r_net * risk_pct / 100.0
        peak = max(peak, eq)
        dd_pct = max(dd_pct, (peak - eq) / peak * 100.0)
    return {"max_drawdown_R": round(dd_r, 3), "max_drawdown_pct": round(dd_pct, 2)}


def cell_metrics(trades: Sequence[SimTrade]) -> Dict[str, Any]:
    out = metrics_block(trades)
    if out.get("n", 0):
        out.update(drawdown(trades))
        out["avg_cost_R"] = round(sum(t.cost_r for t in trades) / len(trades), 4)
        out["avg_funding_R"] = round(sum(t.funding_r for t in trades) / len(trades), 4)
        out["bootstrap"] = cluster_bootstrap_ci(trades, seed=BOOTSTRAP_SEED)
    return out


def confidence_terciles(trades: Sequence[SimTrade]) -> Dict[str, Any]:
    """Informational (spec §g): metrics per tercile of entry confidence."""
    scored = sorted((t for t in trades if t.confidence is not None), key=lambda t: t.confidence)
    if len(scored) < 3:
        return {}
    k = len(scored)
    cuts = [scored[: k // 3], scored[k // 3: 2 * k // 3], scored[2 * k // 3:]]
    return {
        name: {**metrics_block(group), "confidence_range": [group[0].confidence, group[-1].confidence]}
        for name, group in zip(("low", "mid", "high"), cuts)
    }


def split_metrics(trades: Sequence[SimTrade]) -> Dict[str, Any]:
    return {
        "all": cell_metrics(trades),
        BLOCK_IS: cell_metrics([t for t in trades if t.block == BLOCK_IS]),
        BLOCK_OOS: cell_metrics([t for t in trades if t.block == BLOCK_OOS]),
        "confidence_terciles": confidence_terciles(trades),
    }


def verdict(m: Dict[str, Any]) -> Dict[str, Any]:
    """Spec §g verdict, evaluated mechanically on `split_metrics` output."""
    total, ins, oos = m["all"], m[BLOCK_IS], m[BLOCK_OOS]
    n = total.get("n", 0)
    if n < 30:
        return {"verdict": "INCONCLUSIVE", "failed": [f"n_total={n} < 30"]}
    legs = {
        "expectancy_total >= 0.10R": total["expectancy_R"] >= 0.10,
        "CI95 lower > 0": total["bootstrap"]["ci95_cluster"][0] > 0,
        "n_oos >= 10": oos.get("n", 0) >= 10,
        "expectancy_oos > 0": oos.get("n", 0) > 0 and oos["expectancy_R"] > 0,
        "expectancy_is > 0": ins.get("n", 0) > 0 and ins["expectancy_R"] > 0,
        "PF >= 1.2": float(total["profit_factor"]) >= 1.2,
        "maxDD <= 10R": total["max_drawdown_R"] <= 10.0,
    }
    failed = [k for k, ok in legs.items() if not ok]
    return {"verdict": "PASS" if not failed else "NO-PASS", "failed": failed}


def buy_and_hold_pct(df: pd.DataFrame, start: datetime, end: datetime) -> Optional[float]:
    """Context only: % change from the first close in-window to the last."""
    win = df[(df.index >= pd.Timestamp(utc(start))) & (df.index < pd.Timestamp(utc(end)))]
    if len(win) < 2:
        return None
    return round((float(win["close"].iloc[-1]) / float(win["close"].iloc[0]) - 1.0) * 100.0, 2)


def trade_dicts(trades: Sequence[Any]) -> List[Dict[str, Any]]:
    return [asdict(t) for t in trades]


# ----------------------------------------------------------------------
# Round 2: layered position ledger in USDT (re-buys, cross margin, liquidation)
# ----------------------------------------------------------------------
#
# Owner decision 1 (docs/impulsos-v2.md, 2026-11-01): profile PRO, 1300 USDT,
# with RE-BUYS. A trade is no longer one entry + one ATR stop: it is a stack
# of layers on one side, closed together. Additive: round-1 `SimTrade`,
# `simulate_decisions`, `run_legacy`, `run_new` are untouched.

LEDGER_INITIAL_EQUITY = 1300.0
LEDGER_LEVERAGE = 5.0  # pro: 5x cross (mmk-api today)
LEDGER_MAINTENANCE_RATE = 0.005  # liquidation when equity + uPnL <= 0.5% of notional
R_BASIS_LAYER1 = "layer1_invalidation"  # 1R = USDT risk of layer 1 to its invalidation
R_BASIS_EQUITY_PCT = "equity_pct"  # 1R = r_equity_pct % of equity at the first entry
LEDGER_ACTIONS = ("enter", "add_layer", "exit", "hold", "alert", "none")


@dataclass(frozen=True)
class LedgerConfig:
    initial_equity: float = LEDGER_INITIAL_EQUITY
    leverage: float = LEDGER_LEVERAGE
    margin_mode: str = "cross"
    maintenance_rate: float = LEDGER_MAINTENANCE_RATE
    fee: float = DEFAULT_FEE_RATE_PER_SIDE  # per side, per layer (E16)
    slip: float = DEFAULT_SLIPPAGE_PER_SIDE  # per side, per layer (E16)
    funding_rate_per_8h: float = FUNDING_RATE_PER_8H  # on total notional, any sign
    r_basis: str = R_BASIS_LAYER1
    r_equity_pct: float = 0.75  # only for R_BASIS_EQUITY_PCT (pro risk/trade)

    def __post_init__(self) -> None:
        if self.margin_mode not in ("cross", "isolated"):
            raise ValueError("margin_mode must be 'cross' (pro 5x) or 'isolated' (snipper 10x, round 4)")
        if self.leverage <= 0 or self.initial_equity <= 0:
            raise ValueError("leverage and initial_equity must be > 0")
        if self.r_basis not in (R_BASIS_LAYER1, R_BASIS_EQUITY_PCT):
            raise ValueError(f"unknown r_basis {self.r_basis!r}")


@dataclass
class Layer:
    bar: int
    time: str
    price: float
    qty: float  # base units, always > 0 (side lives on the position)
    notional: float  # qty x price at the fill
    margin: float  # notional / leverage
    cost: float  # entry fee + slip in USDT


@dataclass
class LedgerTrade:
    """A closed layered position; duck-types what `cell_metrics` reads."""

    side: str
    entry_time: str
    exit_time: str
    exit_reason: str  # signal_exit | liquidation | end_of_data | <engine exit_* code>
    bars_held: int
    n_layers: int
    layers: List[Dict[str, Any]]
    avg_price: float
    exit_price: float
    qty: float
    notional_max: float
    exposure_max: float  # max notional / equity seen while open
    invalidation: Optional[float]
    pnl_gross_usdt: float
    cost_usdt: float
    funding_usdt: float
    pnl_net_usdt: float
    r_unit_usdt: Optional[float]
    r_net: float
    cost_r: float
    funding_r: float
    equity_after: float
    block: str
    cluster: str
    confidence: Optional[float] = None
    reasons: List[str] = field(default_factory=list)
    partial_takes: List[Dict[str, Any]] = field(default_factory=list)  # round 4 (§R4.d)


class PositionLedger:
    """One book, one side at a time, N layers, cross margin, marked per bar.

    Call order per closed bar: `mark(bar)` first (funding for the bar just
    held, intrabar liquidation check at the adverse extreme, mark-to-market at
    the close), then the bar's decision at its close (`open` / `add_layer` /
    `close`). Costs are E16 per layer per side on the notional; funding is
    charged on the total notional for the time held, whatever its sign.
    """

    def __init__(self, config: LedgerConfig = LedgerConfig(), *, split: Optional[datetime] = None,
                 symbol: str = "") -> None:
        self.cfg = config
        self.split = utc(split) if split is not None else None
        self.symbol = symbol
        self.cash = float(config.initial_equity)  # realised equity
        self.side: Optional[str] = None
        self.layers: List[Layer] = []
        self.trades: List[LedgerTrade] = []
        self.equity_curve: List[Tuple[str, float]] = []
        self.skipped_layers = 0
        self._open: Dict[str, Any] = {}

    # -- state -----------------------------------------------------------------
    @property
    def is_open(self) -> bool:
        return self.side is not None

    @property
    def qty(self) -> float:
        return sum(layer.qty for layer in self.layers)

    @property
    def avg_price(self) -> Optional[float]:
        q = self.qty
        return sum(layer.qty * layer.price for layer in self.layers) / q if q > 0 else None

    def notional(self, price: float) -> float:
        return self.qty * float(price)

    def unrealized(self, price: float) -> float:
        if not self.is_open or not self.layers:
            return 0.0
        sign = 1.0 if self.side == "long" else -1.0
        return sign * self.qty * (float(price) - float(self.avg_price))

    def equity(self, price: Optional[float] = None) -> float:
        return self.cash + (self.unrealized(price) if price is not None and self.is_open else 0.0)

    def exposure(self, price: float) -> float:
        eq = self.equity(price)
        return self.notional(price) / eq if eq > 0 else float("inf")

    @property
    def position_margin(self) -> float:
        """Isolated margin backing the open layers (sum of notional / leverage at fill)."""
        return sum(layer.margin for layer in self.layers)

    def liquidation_price(self) -> Optional[float]:
        """Price where backing + uPnL == maintenance x notional.

        cross: backing = realised wallet (`cash`); isolated: backing = the
        position margin only, so the wallet outside the position is never at
        risk and the distance is set by the leverage (round 4, Bitget isolated:
        long ~ avg x (1 - 1/lev + mmr), short ~ avg x (1 + 1/lev - mmr)).
        """
        if not self.is_open:
            return None
        q, a, m = self.qty, float(self.avg_price), self.cfg.maintenance_rate
        e = self.position_margin if self.cfg.margin_mode == "isolated" else self.cash
        if self.side == "long":
            price = (q * a - e) / (q * (1.0 - m))
            return price if price > 0 else None
        return (e + q * a) / (q * (1.0 + m))

    def _side_cost(self, notional: float) -> float:
        return (self.cfg.fee + self.cfg.slip) * notional

    # -- actions ----------------------------------------------------------------
    def capacity(self, price: float) -> float:
        """Notional that can still be added without exceeding `leverage` x equity
        AFTER paying the layer's own entry cost."""
        lev, c = self.cfg.leverage, self.cfg.fee + self.cfg.slip
        return max(0.0, (lev * self.equity(price) - self.notional(price)) / (1.0 + lev * c))

    def _add(self, bar: int, time_: str, price: float, notional: float) -> Optional[Layer]:
        notional = min(float(notional), self.capacity(price))  # size DOWN, never over-lever
        if not (notional > 0 and price > 0):
            self.skipped_layers += 1
            return None
        cost = self._side_cost(notional)
        layer = Layer(bar=bar, time=time_, price=float(price), qty=notional / float(price),
                      notional=notional, margin=notional / self.cfg.leverage, cost=cost)
        self.cash -= cost
        self.layers.append(layer)
        self._open["cost"] += cost
        self._open["notional_max"] = max(self._open["notional_max"], self.notional(price))
        self._open["exposure_max"] = max(self._open["exposure_max"], self.exposure(price))
        return layer

    def open(self, bar: int, time_: str, side: str, price: float, notional: float, *,
             invalidation: Optional[float] = None, reasons: Optional[List[str]] = None,
             confidence: Optional[float] = None) -> Optional[Layer]:
        if self.is_open:
            raise RuntimeError("position already open: use add_layer or close first")
        if side not in ("long", "short"):
            raise ValueError(f"unknown side {side!r}")
        self.side = side
        self._open = {"bar": bar, "time": time_, "cost": 0.0, "funding": 0.0, "notional_max": 0.0,
                      "exposure_max": 0.0, "invalidation": invalidation, "reasons": list(reasons or []),
                      "confidence": confidence, "equity_at_entry": self.cash}
        layer = self._add(bar, time_, price, notional)
        if layer is None:
            self.side, self._open = None, {}
        else:
            self._open["layer1_qty"] = layer.qty
        return layer

    def add_layer(self, bar: int, time_: str, price: float, notional: float) -> Optional[Layer]:
        if not self.is_open:
            raise RuntimeError("no open position to add a layer to")
        return self._add(bar, time_, price, notional)

    def r_unit(self) -> Optional[float]:
        if not self.layers:
            return None
        if self.cfg.r_basis == R_BASIS_EQUITY_PCT:
            return self._open["equity_at_entry"] * self.cfg.r_equity_pct / 100.0
        inv = self._open.get("invalidation")
        if inv is None:
            return None
        first = self.layers[0]
        # Layer-1 risk at its ORIGINAL qty: a partial take must not shrink the R unit.
        qty1 = self._open.get("layer1_qty", first.qty)
        risk = qty1 * abs(first.price - float(inv))
        return risk if risk > 0 else None

    def reduce(self, bar: int, time_: str, price: float, fraction: float, reason: str = "partial_take") -> Dict[str, Any]:
        """Partial take (round 4): close `fraction` of every layer at `price`.

        Realises the gross PnL of the closed qty, pays the E16 exit cost on the
        closed notional, keeps the layers (scaled) and records the take on the
        open trade. Never closes the position: fraction is clamped to < 1.
        """
        if not self.is_open:
            raise RuntimeError("no open position to reduce")
        fraction = min(max(float(fraction), 0.0), 0.999)
        price = float(price)
        sign = 1.0 if self.side == "long" else -1.0
        closed_qty = 0.0
        gross = 0.0
        for layer in self.layers:
            cut = layer.qty * fraction
            gross += sign * cut * (price - layer.price)
            layer.qty -= cut
            layer.notional -= cut * layer.price
            layer.margin = layer.notional / self.cfg.leverage
            closed_qty += cut
        exit_cost = self._side_cost(closed_qty * price)
        self.cash += gross - exit_cost
        self._open["cost"] += exit_cost
        self._open["partial_gross"] = self._open.get("partial_gross", 0.0) + gross
        take = {"bar": bar, "time": time_, "price": price, "fraction": fraction, "qty": closed_qty,
                "pnl_gross_usdt": round(gross, 4), "cost_usdt": round(exit_cost, 4), "reason": reason}
        self._open.setdefault("partial_takes", []).append(take)
        return take

    def close(self, bar: int, time_: str, price: float, reason: str) -> LedgerTrade:
        if not self.is_open:
            raise RuntimeError("no open position to close")
        price = float(price)
        exit_cost = self._side_cost(self.notional(price))
        gross = self.unrealized(price)
        self.cash += gross - exit_cost
        if reason == "liquidation" and self.cfg.margin_mode == "isolated":
            # Bitget keeps the maintenance remainder as the liquidation clearance
            # fee: the whole isolated margin is lost, never more (wallet outside
            # the position is untouched).
            remainder = max(0.0, self.position_margin + gross)
            self.cash -= remainder
            exit_cost += remainder
        gross += self._open.get("partial_gross", 0.0)  # partial takes already realised
        cost = self._open["cost"] + exit_cost
        funding = self._open["funding"]
        net = gross - cost - funding
        r_unit = self.r_unit()
        first_time = self._open["time"]
        entry_dt = pd.Timestamp(first_time).to_pydatetime()
        trade = LedgerTrade(
            side=self.side, entry_time=first_time, exit_time=time_, exit_reason=reason,
            bars_held=bar - self._open["bar"], n_layers=len(self.layers),
            layers=[asdict(layer) for layer in self.layers],
            avg_price=round(float(self.avg_price), 8), exit_price=round(price, 8),
            qty=round(self.qty, 10), notional_max=round(self._open["notional_max"], 4),
            exposure_max=round(self._open["exposure_max"], 4), invalidation=self._open["invalidation"],
            pnl_gross_usdt=round(gross, 4), cost_usdt=round(cost, 4), funding_usdt=round(funding, 4),
            pnl_net_usdt=round(net, 4), r_unit_usdt=round(r_unit, 4) if r_unit else None,
            r_net=round(net / r_unit, 6) if r_unit else 0.0,
            cost_r=round(cost / r_unit, 6) if r_unit else 0.0,
            funding_r=round(funding / r_unit, 6) if r_unit else 0.0,
            equity_after=round(self.cash, 4),
            block=BLOCK_IS if self.split is None or utc(entry_dt) < self.split else BLOCK_OOS,
            cluster=f"{self.symbol}|{utc(entry_dt):%Y-%m}",
            confidence=self._open["confidence"], reasons=self._open["reasons"],
            partial_takes=list(self._open.get("partial_takes", [])),
        )
        self.trades.append(trade)
        self.side, self.layers, self._open = None, [], {}
        return trade

    def mark(self, bar: int, time_: str, *, high: float, low: float, close: float,
             hours: float) -> Optional[LedgerTrade]:
        """Funding for `hours` held, liquidation at the adverse extreme, then MTM at close."""
        if self.is_open:
            funding = self.cfg.funding_rate_per_8h * (hours / 8.0) * self.notional(close)
            self.cash -= funding
            self._open["funding"] += funding
            liq = self.liquidation_price()
            adverse = low if self.side == "long" else high
            if liq is not None and ((self.side == "long" and adverse <= liq) or (self.side == "short" and adverse >= liq)):
                trade = self.close(bar, time_, liq, "liquidation")
                self.equity_curve.append((time_, self.cash))
                return trade
            self._open["exposure_max"] = max(self._open["exposure_max"], self.exposure(close))
        self.equity_curve.append((time_, self.equity(close)))
        return None


@dataclass(frozen=True)
class LayerSizing:
    """How big each layer is (phase B binds it to the trading spec).

    * layer 1: risk-based when the decision carries an invalidation
      (`risk_pct` of equity / distance to it), else `first_notional_x` x equity;
    * add_layer: `add_notional_x` x layer-1 notional; a decision field
      `notional` (USDT) overrides both. The ledger caps every layer at the
      leverage capacity (size down, never widen the stop).
    """

    risk_pct: float = 0.75
    first_notional_x: float = 1.0
    add_notional_x: float = 1.0


def _decision_time(df: pd.DataFrame, i: int) -> str:
    return df.index[i].isoformat()


def simulate_ledger(
    df: pd.DataFrame,
    decisions: Sequence[Any],
    *,
    split: datetime,
    start: datetime,
    end: datetime,
    timeframe: str,
    symbol: str = "",
    config: LedgerConfig = LedgerConfig(),
    sizing: LayerSizing = LayerSizing(),
    directions: Sequence[str] = ("long", "short"),
) -> Dict[str, Any]:
    """Drive a `PositionLedger` from per-bar decisions (`action` in LEDGER_ACTIONS).

    Per bar: mark (funding, liquidation, MTM) -> decision at the close:
    `enter` opens layer 1 when flat (side in `directions`, bar in
    [start, end)); `add_layer` adds on the open side; `exit` closes all
    layers at `exit_price` (engine fill, e.g. a gapped stop) or the close;
    `hold` / `alert` / `none` do nothing. An `enter` of the opposite side
    while open closes (no same-bar flip). Still open at the end ->
    `end_of_data`. Decisions are matched to bars by their `timestamp` (open ms).
    """
    by_bar: Dict[int, Any] = {}
    for d in decisions:
        i = _bar_index_for(df, _field(d, "timestamp"), timeframe)
        if i is not None:
            by_bar[i] = d
    ledger = PositionLedger(config, split=split, symbol=symbol)
    start_ts, end_ts = pd.Timestamp(utc(start)), pd.Timestamp(utc(end))
    highs, lows = df["high"].to_numpy(float), df["low"].to_numpy(float)
    closes = df["close"].to_numpy(float)
    hours = TIMEFRAME_MS[timeframe] / 3_600_000.0
    actions: Dict[str, int] = {}
    first_notional = 0.0
    last = len(df) - 1

    for i in range(len(df)):
        t = _decision_time(df, i)
        ledger.mark(i, t, high=highs[i], low=lows[i], close=closes[i], hours=hours)
        d = by_bar.get(i)
        if d is None:
            continue
        action = str(_field(d, "action", "") or "").lower()
        actions[action] = actions.get(action, 0) + 1
        side = normalise_side(_field(d, "side"))
        price = float(closes[i])
        override = _field(d, "notional")
        if ledger.is_open:
            reasons = [r for r in (_field(d, "reasons", []) or []) if str(r).startswith("exit_")]
            if action == "exit" and side in (None, ledger.side):
                fill = _field(d, "exit_price")
                ledger.close(i, t, float(fill) if fill is not None else price,
                             reasons[0] if reasons else "signal_exit")
            elif action == "enter" and side is not None and side != ledger.side:
                ledger.close(i, t, price, "opposite_signal")
            elif action == "add_layer" and side in (None, ledger.side):
                size = float(override) if override is not None else sizing.add_notional_x * first_notional
                ledger.add_layer(i, t, price, size)
            continue
        if action != "enter" or side not in directions or i >= last:
            continue
        if not (start_ts <= df.index[i] < end_ts):
            continue
        inv = _field(d, "stop_price")
        equity = ledger.equity()
        if override is not None:
            size = float(override)
        elif inv is not None and abs(price - float(inv)) > 0:
            size = equity * sizing.risk_pct / 100.0 / (abs(price - float(inv)) / price)
        else:
            size = sizing.first_notional_x * equity
        conf = _field(d, "confidence")
        layer = ledger.open(i, t, side, price, size, invalidation=float(inv) if inv is not None else None,
                            reasons=list(_field(d, "reasons", []) or []),
                            confidence=float(conf) if conf is not None else None)
        first_notional = layer.notional if layer is not None else 0.0

    if ledger.is_open:
        ledger.close(last, _decision_time(df, last), float(closes[last]), "end_of_data")
    return {"ledger": ledger, "trades": list(ledger.trades), "decisions": actions}


# ----------------------------------------------------------------------
# Round 2: sequential machine (impulse_sequential) driven bar by bar with the ledger
# ----------------------------------------------------------------------

def load_sequential_frames(params: Any, loader: Callable[[str], pd.DataFrame]) -> Tuple[Dict[str, pd.DataFrame], Dict[str, str]]:
    """Trigger + context frames enriched with the TV indicators; a context TF that
    cannot be loaded (e.g. 1M on bitget) degrades to NaN bias, as in the live path."""
    frames: Dict[str, pd.DataFrame] = {params.trigger_tf: enrich_tv(loader(params.trigger_tf))}
    status: Dict[str, str] = {params.trigger_tf: "ok"}
    for tf in params.context_order():
        try:
            frames[tf] = enrich_tv(loader(tf))
            status[tf] = "ok"
        except Exception as exc:  # context only
            status[tf] = f"failed:{type(exc).__name__}"
    return frames, status


def _sequential_params(rule: str, profile: str, **overrides: Any) -> Any:
    """`r2` -> `impulse-2.1.0` (`ImpulseParams.sequential`); `r4` -> `impulse-2.2.0` (`r4_params`);
    `r5` -> `impulse-2.3.0` (`r5_params`, `entry_filter` via overrides)."""
    from .impulse_sequential import r4_params, r5_params, sequential_params

    if rule == "r2":
        return sequential_params(profile, **overrides)
    if rule == "r4":
        return r4_params(profile, **overrides)
    if rule == "r5":
        return r5_params(profile, **overrides)
    raise ValueError(f"unknown rule {rule!r} (use 'r2', 'r4' or 'r5')")


def ledger_for(params: Any, *, split: datetime, symbol: str,
               fee: float = DEFAULT_FEE_RATE_PER_SIDE, slip: float = DEFAULT_SLIPPAGE_PER_SIDE) -> PositionLedger:
    cfg = LedgerConfig(initial_equity=float(params.equity_usdt), leverage=float(params.leverage),
                       margin_mode=params.margin_mode, maintenance_rate=float(params.maintenance_margin_rate),
                       fee=fee, slip=slip)
    return PositionLedger(cfg, split=split, symbol=symbol)


def drive_sequential(machine: Any, ledger: PositionLedger, trigger_df: pd.DataFrame, *, first: int,
                     timeframe: str, forced: Optional[Tuple[int, str]] = None) -> Dict[str, Any]:
    """Step the machine and the ledger together over closed candles `first..last`.

    Per candle: `ledger.mark` (funding, intrabar liquidation -> `machine.force_flat`,
    MTM) -> machine decision at the close with the ledger's realised equity as
    sizing base -> ledger fill (`enter` opens layer 1 with the decision's
    `notional` and invalidation, `add_layer` adds, `exit` closes all layers at
    the close). `forced=(bar, side)` replaces the machine decision of that bar
    by `force_enter` (§R2.g anchored replay). An `enter` on the very last
    candle is not filled (no next bar). Still open at the end -> `end_of_data`,
    with the open book snapshot returned in `open_at_end`.
    """
    highs, lows = trigger_df["high"].to_numpy(float), trigger_df["low"].to_numpy(float)
    closes = trigger_df["close"].to_numpy(float)
    hours = TIMEFRAME_MS[timeframe] / 3_600_000.0
    last = len(trigger_df) - 1
    decisions: List[Any] = []
    actions: Dict[str, int] = {}
    liquidations = 0
    for i in range(first, len(trigger_df)):
        t = trigger_df.index[i].isoformat()
        liq = ledger.mark(i, t, high=highs[i], low=lows[i], close=closes[i], hours=hours)
        if liq is not None:
            liquidations += 1
            machine.force_flat(i, "liquidation")
        if forced is not None and i == forced[0]:
            d = machine.force_enter(i, forced[1], equity=ledger.cash)
        else:
            d = machine.step(i, equity=ledger.cash)
        decisions.append(d)
        actions[d.action] = actions.get(d.action, 0) + 1
        price = float(closes[i])
        if d.action == "enter":
            if i >= last:
                machine.force_flat(i, "end_of_data")
                d.reasons.append("entry_skipped_last_candle")
                continue
            ledger.open(i, t, d.side, price, float(d.notional), invalidation=d.invalidation_price,
                        reasons=list(d.reasons), confidence=d.confidence)
        elif d.action == "add_layer" and ledger.is_open:
            ledger.add_layer(i, t, price, float(d.notional))
        elif d.action == "reduce" and ledger.is_open:
            ledger.reduce(i, t, price, float(d.context.get("reduce_fraction", 0.0)), "partial_take_mlrsi")
        elif d.action == "exit" and ledger.is_open:
            codes = [r for r in d.reasons if str(r).startswith("exit_")]
            ledger.close(i, t, price, codes[0] if codes else "signal_exit")
    open_at_end: Optional[Dict[str, Any]] = None
    if ledger.is_open:
        close_last = float(closes[last])
        notional_now = ledger.notional(close_last)
        open_at_end = {
            "side": ledger.side, "qty": ledger.qty, "avg_price": ledger.avg_price, "n_layers": len(ledger.layers),
            "layers": [asdict(l) for l in ledger.layers], "last_close": close_last,
            "unrealized_gross_usdt": round(ledger.unrealized(close_last), 4),
            "entry_costs_usdt": round(ledger._open["cost"], 4), "funding_usdt": round(ledger._open["funding"], 4),
            "exit_cost_estimate_usdt": round(ledger._side_cost(notional_now), 4),
            "r_unit_usdt": ledger.r_unit(), "invalidation": ledger._open.get("invalidation"),
            "equity_mtm": round(ledger.equity(close_last), 4),
        }
        open_at_end["unrealized_net_usdt"] = round(
            open_at_end["unrealized_gross_usdt"] - open_at_end["entry_costs_usdt"] - open_at_end["funding_usdt"]
            - open_at_end["exit_cost_estimate_usdt"], 4)
        ledger.close(last, trigger_df.index[last].isoformat(), close_last, "end_of_data")
    return {"decisions": decisions, "actions": actions, "liquidations": liquidations, "open_at_end": open_at_end}


def run_sequential(
    *, profile: str, symbol: str, start: datetime, end: datetime, split: datetime,
    directions: Sequence[str], loader: Callable[[str], pd.DataFrame], mlrsi_gate: bool = False,
    overrides: Optional[Dict[str, Any]] = None, fee: float = DEFAULT_FEE_RATE_PER_SIDE,
    slip: float = DEFAULT_SLIPPAGE_PER_SIDE, rule: str = "r2",
) -> Dict[str, Any]:
    """Round-2 cell run: `ImpulseParams.sequential(profile)` (+ `mlrsi_gate` for H2) over
    the cached frames, one book long-or-short, scored by the layered ledger
    (1R = layer-1 risk to the invalidation = 2% E0 unless the exposure cap binds).
    `rule="r4"` builds `impulse-2.2.0` params (`impulse_sequential.r4_params`) instead."""
    from .impulse_sequential import SequentialMachine

    params = _sequential_params(rule, profile, mlrsi_gate=mlrsi_gate, **(overrides or {}))
    frames, status = load_sequential_frames(params, loader)
    trigger_df = frames[params.trigger_tf]
    first = max(WARMUP_BARS, int(trigger_df.index.searchsorted(pd.Timestamp(utc(start)))))
    machine = SequentialMachine(params, frames, equity=params.equity_usdt)
    ledger = ledger_for(params, split=split, symbol=symbol, fee=fee, slip=slip)
    run = drive_sequential(machine, ledger, trigger_df, first=first, timeframe=params.trigger_tf)
    trades = [t for t in ledger.trades if t.side in directions]
    return {
        "profile": profile, "variant": "H2" if mlrsi_gate else "H1", "params": asdict(params),
        "timeframes": {"trigger": params.trigger_tf, "confirm": params.confirm_tf, "context": list(params.context_order())},
        "tf_status": status, "first_bar": trigger_df.index[first].isoformat(), "decisions": run["actions"],
        "liquidations": run["liquidations"], "trades": trades, "ledger": ledger, "all_decisions": run["decisions"],
        "frames": frames, "buy_and_hold_pct": buy_and_hold_pct(trigger_df, start, end),
        "rule_version": params.rule_version,
    }


def run_anchored(
    *, profile: str, frames: Mapping[str, pd.DataFrame], anchor_bar: int, side: str, symbol: str,
    split: datetime, mlrsi_gate: bool = False, fee: float = DEFAULT_FEE_RATE_PER_SIDE,
    slip: float = DEFAULT_SLIPPAGE_PER_SIDE, rule: str = "r2", overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """§R2.g.4: force layer 1 at `anchor_bar` close, then the real re-buy / exit rules to the end."""
    from .impulse_sequential import SequentialMachine

    params = _sequential_params(rule, profile, mlrsi_gate=mlrsi_gate, **(overrides or {}))
    trigger_df = frames[params.trigger_tf]
    machine = SequentialMachine(params, frames, equity=params.equity_usdt)
    ledger = ledger_for(params, split=split, symbol=symbol, fee=fee, slip=slip)
    run = drive_sequential(machine, ledger, trigger_df, first=anchor_bar, timeframe=params.trigger_tf,
                           forced=(anchor_bar, side))
    return {"decisions": run["decisions"], "actions": run["actions"], "trades": list(ledger.trades),
            "open_at_end": run["open_at_end"], "liquidations": run["liquidations"]}


def equity_drawdown_pct(curve: Sequence[Tuple[str, float]]) -> float:
    peak, dd = None, 0.0
    for _, eq in curve:
        peak = eq if peak is None else max(peak, eq)
        if peak and peak > 0:
            dd = max(dd, (peak - eq) / peak * 100.0)
    return round(dd, 2)


def ledger_metrics(ledger: PositionLedger, trades: Optional[Sequence[LedgerTrade]] = None) -> Dict[str, Any]:
    """USDT-level metrics of a ledger run (+ the R metrics of `cell_metrics`)."""
    trades = list(ledger.trades if trades is None else trades)
    reasons: Dict[str, int] = {}
    for t in trades:
        reasons[t.exit_reason] = reasons.get(t.exit_reason, 0) + 1
    out: Dict[str, Any] = {
        "n": len(trades),
        "initial_equity": ledger.cfg.initial_equity,
        "equity_final": round(ledger.cash, 2),
        "pnl_total_usdt": round(sum(t.pnl_net_usdt for t in trades), 2),
        "return_pct": round((ledger.cash / ledger.cfg.initial_equity - 1.0) * 100.0, 2),
        "max_drawdown_equity_pct": equity_drawdown_pct(ledger.equity_curve),
        "liquidations": reasons.get("liquidation", 0),
        "avg_layers": round(sum(t.n_layers for t in trades) / len(trades), 2) if trades else 0.0,
        "max_exposure_x": round(max((t.exposure_max for t in trades), default=0.0), 3),
        "skipped_layers": ledger.skipped_layers,
        "partial_takes": sum(len(t.partial_takes) for t in trades),
        "exit_reasons": reasons,
        "cost_usdt": round(sum(t.cost_usdt for t in trades), 2),
        "funding_usdt": round(sum(t.funding_usdt for t in trades), 2),
    }
    scored = [t for t in trades if t.r_unit_usdt]
    out["r_metrics"] = cell_metrics(scored) if scored else {"n": 0}
    return out
