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
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

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


def trade_dicts(trades: Sequence[SimTrade]) -> List[Dict[str, Any]]:
    return [asdict(t) for t in trades]
