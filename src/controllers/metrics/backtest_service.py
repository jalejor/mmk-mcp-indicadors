"""Backtest engine that replays the RulesService strategy over historical OHLCV.

Design goals:
* Strict no-peek-ahead: at each bar `i` the indicator and rule services only
  see the slice `df.iloc[: i + 1]`, never future data.
* ATR-based stops/targets and risk-per-trade quantity sizing, numerically
  identical to the live MovementsService. Both services pull
  `(atr_mult_stop, r_multiple_target)` from the shared `sizing_profiles`
  module keyed by `risk_profile` (low/medium/high -> 1.0/1.5/2.0 and 2/3/4),
  so the same symbol + ATR + equity + risk_profile yields the same
  stop_distance, target and quantity in live and backtest. Callers may still
  override `atr_stop_multiplier`/`target_r_multiple` explicitly to sweep
  parameters; when omitted they are derived from `risk_profile` (default
  "medium" -> 1.5/3.0, the historical defaults, so existing behaviour is
  unchanged).
* Pure-python metrics so the result is JSON-serialisable for the HTTP and
  MCP layers without extra dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from math import sqrt
from typing import Any, Dict, List, Literal, Optional

import math

import pandas as pd

from .indicators_service import IndicatorsService
from .market_data_service import DEFAULT_EXCHANGE, MarketDataService
from .rules_service import RulesService
from .sizing_profiles import RiskProfile, atr_sizing_for

Side = Literal["long", "short", "both"]


# Approximate number of bars per year for the supported timeframes; used to
# annualise the Sharpe ratio without introducing a calendar dependency.
_BARS_PER_YEAR = {
    "1m": 60 * 24 * 365,
    "5m": 12 * 24 * 365,
    "15m": 4 * 24 * 365,
    "30m": 2 * 24 * 365,
    "1h": 24 * 365,
    "2h": 12 * 365,
    "4h": 6 * 365,
    "6h": 4 * 365,
    "8h": 3 * 365,
    "12h": 2 * 365,
    "1d": 365,
    "3d": 121,
    "1w": 52,
}

# Approximate timeframe -> milliseconds, used when paginating ccxt fetches.
_TIMEFRAME_MS = {
    "1m": 60_000,
    "5m": 5 * 60_000,
    "15m": 15 * 60_000,
    "30m": 30 * 60_000,
    "1h": 60 * 60_000,
    "2h": 2 * 60 * 60_000,
    "4h": 4 * 60 * 60_000,
    "6h": 6 * 60 * 60_000,
    "8h": 8 * 60 * 60_000,
    "12h": 12 * 60 * 60_000,
    "1d": 24 * 60 * 60_000,
    "3d": 3 * 24 * 60 * 60_000,
    "1w": 7 * 24 * 60 * 60_000,
}


@dataclass
class Trade:
    entry_time: datetime
    exit_time: Optional[datetime]
    side: str  # "long" | "short"
    entry_price: float
    exit_price: float
    stop_price: float
    target_price: float
    size: float  # quantity in base asset
    pnl_dollars: float
    pnl_pct: float
    r_multiple: float
    exit_reason: str  # "target" | "stop" | "end_of_data"
    reasons_at_entry: List[str] = field(default_factory=list)
    bars_held: int = 0


class BacktestService:
    def __init__(
        self,
        *,
        symbol: str,
        timeframe: str = "1h",
        exchange: str = DEFAULT_EXCHANGE,
        start: datetime,
        end: datetime,
        initial_capital: float = 10000.0,
        risk_per_trade_pct: float = 1.5,
        risk_profile: RiskProfile = "medium",
        atr_stop_multiplier: Optional[float] = None,
        target_r_multiple: Optional[float] = None,
        max_concurrent_positions: int = 1,
        side: Side = "both",
        warmup_bars: int = 250,
    ) -> None:
        if start >= end:
            raise ValueError("start must be before end")
        if max_concurrent_positions < 1:
            raise ValueError("max_concurrent_positions must be >= 1")

        # Sizing comes from the shared profile table keyed by `risk_profile`,
        # the same source the live MovementsService uses. Explicit
        # atr_stop_multiplier/target_r_multiple still win when provided so the
        # caller can sweep parameters independently of the profile.
        profile_atr_mult, profile_r_multiple = atr_sizing_for(risk_profile)

        self.symbol = symbol
        self.timeframe = timeframe
        self.exchange = exchange
        self.start = self._ensure_utc(start)
        self.end = self._ensure_utc(end)
        self.initial_capital = float(initial_capital)
        self.risk_per_trade_pct = float(risk_per_trade_pct)
        self.risk_profile: RiskProfile = risk_profile
        self.atr_stop_multiplier = (
            float(atr_stop_multiplier) if atr_stop_multiplier is not None else profile_atr_mult
        )
        self.target_r_multiple = (
            float(target_r_multiple) if target_r_multiple is not None else profile_r_multiple
        )
        self.max_concurrent_positions = max_concurrent_positions
        self.side = side
        self.warmup_bars = max(50, warmup_bars)

    # ------------------------------------------------------------------
    # Public entrypoint
    # ------------------------------------------------------------------
    def run(self) -> Dict[str, Any]:
        df = self._load_history()
        if len(df) <= self.warmup_bars + 1:
            raise ValueError(
                f"Not enough history: got {len(df)} bars, need > {self.warmup_bars + 1}"
            )

        rules_service = RulesService(symbol=self.symbol)
        equity = self.initial_capital
        equity_curve: List[Dict[str, Any]] = []
        trades: List[Trade] = []
        open_trades: List[Trade] = []

        for i in range(self.warmup_bars, len(df)):
            slice_df = df.iloc[: i + 1]
            bar = slice_df.iloc[-1]
            bar_time = slice_df.index[-1].to_pydatetime()

            # Manage already-open trades against the current bar before
            # considering new entries — this prevents the same bar from both
            # opening and closing a trade with peek-ahead bias.
            still_open: List[Trade] = []
            for trade in open_trades:
                outcome = self._update_open_trade(trade, bar, bar_time)
                if outcome is None:
                    trade.bars_held += 1
                    still_open.append(trade)
                else:
                    equity += trade.pnl_dollars
                    trades.append(trade)
            open_trades = still_open

            # Skip new entries until the warm-up phase is complete.
            if bar_time < self.start:
                equity_curve.append({"time": bar_time.isoformat(), "equity": equity})
                continue

            # Don't open new trades on the very last bar — there's nothing to
            # exit them with.
            if i == len(df) - 1:
                equity_curve.append({"time": bar_time.isoformat(), "equity": equity})
                continue

            if len(open_trades) >= self.max_concurrent_positions:
                equity_curve.append({"time": bar_time.isoformat(), "equity": equity})
                continue

            indicators = IndicatorsService(slice_df).calculate_all()
            rules = rules_service.evaluate(indicators)
            signal = rules.get("signal")
            atr = float(indicators.get("atr") or 0.0)
            if atr <= 0:
                equity_curve.append({"time": bar_time.isoformat(), "equity": equity})
                continue

            new_trade = self._maybe_open_trade(
                signal=signal,
                rules=rules,
                bar=bar,
                bar_time=bar_time,
                atr=atr,
                equity=equity,
            )
            if new_trade is not None:
                open_trades.append(new_trade)

            equity_curve.append({"time": bar_time.isoformat(), "equity": equity})

        # Close any remaining open trades on the last close.
        if open_trades:
            last_close = float(df.iloc[-1]["close"])
            last_time = df.index[-1].to_pydatetime()
            for trade in open_trades:
                self._force_close(trade, last_close, last_time, "end_of_data")
                equity += trade.pnl_dollars
                trades.append(trade)
            equity_curve.append({"time": last_time.isoformat(), "equity": equity})

        metrics = self._summarise(trades, equity_curve)
        metrics["trades"] = [self._serialise_trade(t) for t in trades]
        metrics["equity_curve"] = equity_curve
        metrics["initial_capital"] = self.initial_capital
        metrics["final_equity"] = equity
        metrics["symbol"] = self.symbol
        metrics["timeframe"] = self.timeframe
        return metrics

    # ------------------------------------------------------------------
    # Trade lifecycle helpers
    # ------------------------------------------------------------------
    def _maybe_open_trade(
        self,
        *,
        signal: Optional[str],
        rules: Dict[str, Any],
        bar: pd.Series,
        bar_time: datetime,
        atr: float,
        equity: float,
    ) -> Optional[Trade]:
        entry_price = float(bar["close"])
        stop_distance = atr * self.atr_stop_multiplier
        if stop_distance <= 0:
            return None

        risk_dollars = equity * (self.risk_per_trade_pct / 100.0)
        if risk_dollars <= 0:
            return None
        size = risk_dollars / stop_distance

        long_allowed = self.side in ("long", "both")
        short_allowed = self.side in ("short", "both")

        if signal == "entry" and long_allowed:
            target_price = entry_price + stop_distance * self.target_r_multiple
            stop_price = entry_price - stop_distance
            return Trade(
                entry_time=bar_time,
                exit_time=None,
                side="long",
                entry_price=entry_price,
                exit_price=0.0,
                stop_price=stop_price,
                target_price=target_price,
                size=size,
                pnl_dollars=0.0,
                pnl_pct=0.0,
                r_multiple=0.0,
                exit_reason="",
                reasons_at_entry=list(rules.get("support_entry", [])),
            )
        if signal == "exit" and short_allowed:
            target_price = entry_price - stop_distance * self.target_r_multiple
            stop_price = entry_price + stop_distance
            return Trade(
                entry_time=bar_time,
                exit_time=None,
                side="short",
                entry_price=entry_price,
                exit_price=0.0,
                stop_price=stop_price,
                target_price=target_price,
                size=size,
                pnl_dollars=0.0,
                pnl_pct=0.0,
                r_multiple=0.0,
                exit_reason="",
                reasons_at_entry=list(rules.get("support_exit", [])),
            )
        return None

    def _update_open_trade(
        self,
        trade: Trade,
        bar: pd.Series,
        bar_time: datetime,
    ) -> Optional[str]:
        high = float(bar["high"])
        low = float(bar["low"])
        if trade.side == "long":
            stop_hit = low <= trade.stop_price
            target_hit = high >= trade.target_price
            if stop_hit and target_hit:
                # Worst-case assumption: stop fires first.
                return self._close_trade(trade, trade.stop_price, bar_time, "stop")
            if stop_hit:
                return self._close_trade(trade, trade.stop_price, bar_time, "stop")
            if target_hit:
                return self._close_trade(trade, trade.target_price, bar_time, "target")
            return None

        # short
        stop_hit = high >= trade.stop_price
        target_hit = low <= trade.target_price
        if stop_hit and target_hit:
            return self._close_trade(trade, trade.stop_price, bar_time, "stop")
        if stop_hit:
            return self._close_trade(trade, trade.stop_price, bar_time, "stop")
        if target_hit:
            return self._close_trade(trade, trade.target_price, bar_time, "target")
        return None

    def _close_trade(
        self,
        trade: Trade,
        exit_price: float,
        exit_time: datetime,
        reason: str,
    ) -> str:
        trade.exit_price = float(exit_price)
        trade.exit_time = exit_time
        trade.exit_reason = reason
        if trade.side == "long":
            trade.pnl_dollars = (exit_price - trade.entry_price) * trade.size
            stop_distance = trade.entry_price - trade.stop_price
        else:
            trade.pnl_dollars = (trade.entry_price - exit_price) * trade.size
            stop_distance = trade.stop_price - trade.entry_price
        trade.pnl_pct = (trade.pnl_dollars / max(trade.entry_price * trade.size, 1e-9)) * 100.0
        if stop_distance > 0:
            risk_dollars = stop_distance * trade.size
            trade.r_multiple = trade.pnl_dollars / risk_dollars
        return reason

    def _force_close(self, trade: Trade, price: float, when: datetime, reason: str) -> None:
        self._close_trade(trade, price, when, reason)

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------
    def _summarise(
        self,
        trades: List[Trade],
        equity_curve: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        total = len(trades)
        wins = [t for t in trades if t.pnl_dollars > 0]
        losses = [t for t in trades if t.pnl_dollars <= 0]
        win_rate = (len(wins) / total) if total else 0.0
        avg_win_r = (sum(t.r_multiple for t in wins) / len(wins)) if wins else 0.0
        avg_loss_r = (sum(t.r_multiple for t in losses) / len(losses)) if losses else 0.0
        expectancy_r = win_rate * avg_win_r - (1 - win_rate) * abs(avg_loss_r)
        sum_wins = sum(t.pnl_dollars for t in wins)
        sum_losses_abs = abs(sum(t.pnl_dollars for t in losses))
        profit_factor = (sum_wins / sum_losses_abs) if sum_losses_abs > 0 else float("inf") if sum_wins > 0 else 0.0
        total_pnl = sum(t.pnl_dollars for t in trades)
        total_pnl_pct = (total_pnl / self.initial_capital) * 100.0

        # Streaks
        longest_win = longest_loss = current_win = current_loss = 0
        for t in trades:
            if t.pnl_dollars > 0:
                current_win += 1
                current_loss = 0
                longest_win = max(longest_win, current_win)
            else:
                current_loss += 1
                current_win = 0
                longest_loss = max(longest_loss, current_loss)

        # Max drawdown over equity curve.
        peak = self.initial_capital
        max_dd = 0.0
        for point in equity_curve:
            eq = point["equity"]
            if eq > peak:
                peak = eq
            if peak > 0:
                dd = (peak - eq) / peak * 100.0
                if dd > max_dd:
                    max_dd = dd

        # Sharpe ratio annualised from per-bar returns of the equity curve.
        sharpe = 0.0
        if len(equity_curve) > 1:
            equities = [p["equity"] for p in equity_curve]
            returns = [
                (equities[i] - equities[i - 1]) / equities[i - 1]
                for i in range(1, len(equities))
                if equities[i - 1] > 0
            ]
            if returns:
                mean_r = sum(returns) / len(returns)
                var_r = sum((r - mean_r) ** 2 for r in returns) / len(returns)
                std_r = sqrt(var_r) if var_r > 0 else 0.0
                if std_r > 0:
                    bars_per_year = _BARS_PER_YEAR.get(self.timeframe, 24 * 365)
                    sharpe = (mean_r / std_r) * sqrt(bars_per_year)

        avg_duration = (sum(t.bars_held for t in trades) / total) if total else 0.0

        return {
            "total_trades": total,
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate": round(win_rate, 4),
            "avg_win_R": round(avg_win_r, 3),
            "avg_loss_R": round(avg_loss_r, 3),
            "expectancy_R": round(expectancy_r, 4),
            "profit_factor": round(profit_factor, 3) if math.isfinite(profit_factor) else profit_factor,
            "total_pnl_dollars": round(total_pnl, 2),
            "total_pnl_pct": round(total_pnl_pct, 2),
            "max_drawdown_pct": round(max_dd, 2),
            "longest_winning_streak": longest_win,
            "longest_losing_streak": longest_loss,
            "sharpe_ratio": round(sharpe, 3),
            "avg_trade_duration_bars": round(avg_duration, 2),
        }

    @staticmethod
    def _serialise_trade(t: Trade) -> Dict[str, Any]:
        d = asdict(t)
        d["entry_time"] = t.entry_time.isoformat() if t.entry_time else None
        d["exit_time"] = t.exit_time.isoformat() if t.exit_time else None
        return d

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------
    def _load_history(self) -> pd.DataFrame:
        warmup_ms = _TIMEFRAME_MS.get(self.timeframe, 60 * 60_000) * self.warmup_bars
        fetch_since_dt = self.start - timedelta(milliseconds=warmup_ms)
        svc = MarketDataService(exchange_name=self.exchange)

        # Try to use the paginated fetch when ccxt supports `since` directly.
        return self._fetch_paginated(svc, fetch_since_dt)

    def _fetch_paginated(
        self,
        svc: MarketDataService,
        since_dt: datetime,
    ) -> pd.DataFrame:
        exchange = svc.exchange
        timeframe_ms = _TIMEFRAME_MS.get(self.timeframe, 60 * 60_000)
        since_ms = int(since_dt.timestamp() * 1000)
        end_ms = int(self.end.timestamp() * 1000)
        # 200, NOT 1000 (known-errors E13): for ranges beyond its recent
        # window bitget routes `since` to the history-candles endpoint, which
        # serves at most 200 rows ending at `since + limit * duration`. With
        # limit=1000 that silently ignores `since` (returns only the latest
        # ~200 candles) or opens a gap; with limit=200 bitget honours `since`
        # exactly, so forward pagination is gap-free (matches SetupBacktestService).
        limit = 200
        all_rows: List[List[Any]] = []
        cursor = since_ms

        while cursor < end_ms:
            batch = exchange.fetch_ohlcv(
                symbol=self.symbol,
                timeframe=self.timeframe,
                since=cursor,
                limit=limit,
            )
            if not batch:
                break
            all_rows.extend(batch)
            last_ts = batch[-1][0]
            next_cursor = last_ts + timeframe_ms
            if next_cursor <= cursor:
                break  # exchange returned older data than asked for
            cursor = next_cursor
            if len(batch) < limit:
                break

        if not all_rows:
            raise ValueError("No OHLCV data returned from exchange")

        df = pd.DataFrame(all_rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df = df.drop_duplicates(subset="timestamp").sort_values("timestamp")
        df.set_index("datetime", inplace=True)
        df = df[df.index <= self.end]
        return df

    @staticmethod
    def _ensure_utc(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
