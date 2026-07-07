"""Multi-TF, setup-driven backtest for the F0 gate (spec §C).

A NEW module on purpose: the legacy `BacktestService` (RulesService scorer,
single TF, zero fees) keeps serving `/v1/backtest` unchanged; this engine
replays the declarative setups from `setup_definitions` with:

* §0.2 multi-TF alignment (context candle = last CLOSED candle of the higher
  TF at the trigger candle's close time — no cross-TF lookahead),
* a fee/slippage model as config parameters (owner Q9: base model bitget
  spot taker 0.10% + 0.05% slippage per side),
* longs + mirrored shorts (owner Q8),
* chronological 70/30 in/out-of-sample split,
* vetoed-signal logging with counterfactual replay (what the vetoed entries
  would have returned) and a 3-vs-5 veto-window comparison (owner Q10),
* A/B stratification of the confirming `adx_turn` grade,
* live/backtest sizing parity via `sizing_profiles` (same ATR stop/target
  model as `MovementsService`).

Performance note: indicator columns are computed ONCE over the full series
(`IndicatorsService` keeps them on its internal frame). Every indicator used
is causal (rolling/recursive over past bars only), so the value at bar i is
identical whether computed on the full series or on the slice [:i+1] — the
per-bar evaluation then works on cheap slices instead of re-running
pandas-ta per bar like the legacy engine (O(n) instead of O(n^2)).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd

from .indicators_service import IndicatorsService
from .market_data_service import DEFAULT_EXCHANGE, MarketDataService
from .setup_definitions import DEFAULT_SETUPS, SetupDefinition, VetoDefinition, validate_setup
from .setup_service import TIMEFRAME_SECONDS, SetupService
from .sizing_profiles import RiskProfile, atr_sizing_for

# Base fee model (owner Q9, under review — parameters, never constants in code
# paths): bitget spot taker 0.10% + 0.05% slippage, per side.
DEFAULT_FEE_RATE_PER_SIDE = 0.001
DEFAULT_SLIPPAGE_PER_SIDE = 0.0005

# Veto windows replayed counterfactually (owner Q10: active=5, compare vs 3).
VETO_WINDOWS_COMPARED = (3, 5)


@dataclass
class CandidateSignal:
    """A trigger that survived invalidation + context (pre-veto)."""

    setup_id: str
    side: str
    bar_index: int
    entry_time: datetime
    entry_price: float
    atr: float
    veto_reasons: List[str] = field(default_factory=list)
    vetoed_by_window: Dict[int, bool] = field(default_factory=dict)
    adx_turn_grade: Optional[str] = None
    support: List[str] = field(default_factory=list)
    # Hypothetical outcome (size-independent, net of fees):
    r_net: float = 0.0
    exit_reason: str = ""
    exit_time: Optional[datetime] = None
    bars_held: int = 0
    stop_price: float = 0.0
    target_price: float = 0.0
    exit_price: float = 0.0


@dataclass
class ExecutedTrade:
    candidate: CandidateSignal
    size: float
    risk_dollars: float
    pnl_gross: float
    fees_paid: float
    pnl_net: float
    equity_after: float


class SetupBacktestService:
    """Replays the declarative setups over history and reports the §C matrix."""

    def __init__(
        self,
        *,
        symbol: str,
        start: datetime,
        end: datetime,
        exchange: str = DEFAULT_EXCHANGE,
        setups: Optional[Sequence[SetupDefinition]] = None,
        initial_capital: float = 10000.0,
        risk_per_trade_pct: float = 1.5,
        risk_profile: RiskProfile = "medium",
        fee_rate_per_side: float = DEFAULT_FEE_RATE_PER_SIDE,
        slippage_per_side: float = DEFAULT_SLIPPAGE_PER_SIDE,
        in_sample_fraction: float = 0.7,
        warmup_bars: int = 300,
    ) -> None:
        if start >= end:
            raise ValueError("start must be before end")
        if not 0.0 < in_sample_fraction < 1.0:
            raise ValueError("in_sample_fraction must be inside (0, 1)")

        self.symbol = symbol
        self.exchange = exchange
        self.start = self._ensure_utc(start)
        self.end = self._ensure_utc(end)
        self.setups = list(setups) if setups is not None else list(DEFAULT_SETUPS)
        for setup in self.setups:
            validate_setup(setup)
        self.initial_capital = float(initial_capital)
        self.risk_per_trade_pct = float(risk_per_trade_pct)
        self.risk_profile: RiskProfile = risk_profile
        self.atr_stop_multiplier, self.target_r_multiple = atr_sizing_for(risk_profile)
        self.fee_rate_per_side = float(fee_rate_per_side)
        self.slippage_per_side = float(slippage_per_side)
        self.in_sample_fraction = float(in_sample_fraction)
        self.warmup_bars = max(50, warmup_bars)
        self._setup_service = SetupService(setups=self.setups)

    # ------------------------------------------------------------------
    # Public entrypoint
    # ------------------------------------------------------------------
    def run(self) -> Dict[str, Any]:
        timeframes = sorted({tf for setup in self.setups for tf in setup.timeframes()})
        frames = {tf: self._load_enriched_frame(tf) for tf in timeframes}

        is_boundary = self.start + (self.end - self.start) * self.in_sample_fraction

        report: Dict[str, Any] = {
            "rule_version": self.setups[0].rule_version if self.setups else "",
            "symbol": self.symbol,
            "exchange": self.exchange,
            "period": {
                "start": self.start.isoformat(),
                "end": self.end.isoformat(),
                "in_sample_end": is_boundary.isoformat(),
                "in_sample_fraction": self.in_sample_fraction,
            },
            "fee_model": {
                "fee_rate_per_side": self.fee_rate_per_side,
                "slippage_per_side": self.slippage_per_side,
            },
            "sizing": {
                "risk_profile": self.risk_profile,
                "atr_stop_multiplier": self.atr_stop_multiplier,
                "target_r_multiple": self.target_r_multiple,
                "risk_per_trade_pct": self.risk_per_trade_pct,
                "initial_capital": self.initial_capital,
            },
            "setups": {},
        }

        for setup in self.setups:
            candidates = self._collect_candidates(setup, frames)
            accepted = [c for c in candidates if not c.veto_reasons]
            trades = self._execute_portfolio(accepted)
            report["setups"][setup.setup_id] = self._summarise_setup(
                setup, candidates, trades, is_boundary
            )

        return report

    # ------------------------------------------------------------------
    # Candidate collection (per setup)
    # ------------------------------------------------------------------
    def _collect_candidates(
        self, setup: SetupDefinition, frames: Dict[str, pd.DataFrame]
    ) -> List[CandidateSignal]:
        trigger_tf = setup.trigger_timeframe
        trigger_df = frames[trigger_tf]
        trigger_duration = pd.Timedelta(seconds=TIMEFRAME_SECONDS[trigger_tf])
        needed_tfs = setup.timeframes()

        candidates: List[CandidateSignal] = []
        previous_armed = False
        n = len(trigger_df)

        for i in range(n):
            bar_time = trigger_df.index[i]
            if bar_time.to_pydatetime() < self.start:
                continue
            if i >= n - 1:
                break  # never open on the very last bar (nothing to exit with)

            close_time = bar_time + trigger_duration
            sliced = {trigger_tf: trigger_df.iloc[: i + 1]}
            skip = False
            for tf in needed_tfs:
                if tf == trigger_tf:
                    continue
                aligned = SetupService.align_context(frames[tf], close_time, tf)
                if len(aligned) < 50:  # not enough context history yet
                    skip = True
                    break
                sliced[tf] = aligned
            if skip:
                previous_armed = False
                continue

            evaluation = self._setup_service.evaluate_setup(setup, sliced)
            armed = evaluation.context_ok and evaluation.trigger_ok and not evaluation.invalidated

            # The trigger "fires on the candle where it first becomes true"
            # (spec §B.0): only rising edges become candidates.
            if armed and not previous_armed:
                atr = float(trigger_df["atr14"].iloc[i]) if "atr14" in trigger_df else 0.0
                entry_price = float(trigger_df["close"].iloc[i])
                if atr > 0 and entry_price > 0:
                    candidate = CandidateSignal(
                        setup_id=setup.setup_id,
                        side=setup.side,
                        bar_index=i,
                        entry_time=bar_time.to_pydatetime(),
                        entry_price=entry_price,
                        atr=atr,
                        veto_reasons=list(evaluation.veto_reasons),
                        adx_turn_grade=evaluation.adx_turn_grade,
                        support=list(evaluation.support),
                    )
                    candidate.vetoed_by_window = self._veto_window_matrix(
                        setup, sliced[trigger_tf], evaluation
                    )
                    self._simulate_outcome(candidate, trigger_df)
                    candidates.append(candidate)
            previous_armed = armed

        return candidates

    def _veto_window_matrix(
        self,
        setup: SetupDefinition,
        trigger_frame: pd.DataFrame,
        evaluation,
    ) -> Dict[int, bool]:
        """Would this candidate be vetoed under each compared window? (Q10)."""
        from .setup_service import evaluate_vetoes

        matrix: Dict[int, bool] = {}
        optional = {c.label() for c in setup.trigger_any_of}
        evidence = evaluation.details.get("trigger_evidence", [])
        for window in VETO_WINDOWS_COMPARED:
            vetoes = tuple(
                replace(v, max_event_age=window, confirm_window=window) for v in setup.vetoes
            )
            reasons, _grade = evaluate_vetoes(
                vetoes,
                trigger_frame,
                band=setup.timeframe_band,
                satisfied_evidence=evidence,
                optional_evidence=optional,
            )
            matrix[window] = bool(reasons)
        return matrix

    # ------------------------------------------------------------------
    # Outcome simulation (size-independent, net R)
    # ------------------------------------------------------------------
    def _simulate_outcome(self, candidate: CandidateSignal, trigger_df: pd.DataFrame) -> None:
        """Walk forward from the entry bar until stop/target/end-of-data.

        Net-R model: fees + slippage are charged per side on the traded
        notional; because quantity divides out of R they reduce to
        `(fee + slip) * (entry_price + exit_price) / stop_distance` R.
        Stop-before-target on the same bar (worst case), like the legacy
        engine.
        """
        stop_distance = candidate.atr * self.atr_stop_multiplier
        entry = candidate.entry_price
        if candidate.side == "long":
            stop_price = entry - stop_distance
            target_price = entry + stop_distance * self.target_r_multiple
        else:
            stop_price = entry + stop_distance
            target_price = entry - stop_distance * self.target_r_multiple
        candidate.stop_price = stop_price
        candidate.target_price = target_price

        exit_price = float(trigger_df["close"].iloc[-1])
        exit_time = trigger_df.index[-1].to_pydatetime()
        exit_reason = "end_of_data"
        bars_held = len(trigger_df) - 1 - candidate.bar_index

        for j in range(candidate.bar_index + 1, len(trigger_df)):
            high = float(trigger_df["high"].iloc[j])
            low = float(trigger_df["low"].iloc[j])
            if candidate.side == "long":
                stop_hit = low <= stop_price
                target_hit = high >= target_price
            else:
                stop_hit = high >= stop_price
                target_hit = low <= target_price
            if stop_hit:  # worst case: stop first even if both hit
                exit_price, exit_reason = stop_price, "stop"
            elif target_hit:
                exit_price, exit_reason = target_price, "target"
            else:
                continue
            exit_time = trigger_df.index[j].to_pydatetime()
            bars_held = j - candidate.bar_index
            break

        if candidate.side == "long":
            gross_per_unit = exit_price - entry
        else:
            gross_per_unit = entry - exit_price
        cost_per_unit = (self.fee_rate_per_side + self.slippage_per_side) * (entry + exit_price)
        candidate.r_net = (gross_per_unit - cost_per_unit) / stop_distance
        candidate.exit_reason = exit_reason
        candidate.exit_time = exit_time
        candidate.exit_price = exit_price
        candidate.bars_held = bars_held

    # ------------------------------------------------------------------
    # Portfolio execution (accepted candidates, 1 concurrent position)
    # ------------------------------------------------------------------
    def _execute_portfolio(self, accepted: List[CandidateSignal]) -> List[ExecutedTrade]:
        """Sequential execution with max 1 concurrent position per setup.

        Candidates arriving while a trade is open are skipped (the legacy
        engine behaves the same via max_concurrent_positions=1).
        """
        equity = self.initial_capital
        trades: List[ExecutedTrade] = []
        busy_until: Optional[datetime] = None

        for candidate in accepted:
            if busy_until is not None and candidate.entry_time < busy_until:
                continue
            stop_distance = candidate.atr * self.atr_stop_multiplier
            risk_dollars = equity * (self.risk_per_trade_pct / 100.0)
            if stop_distance <= 0 or risk_dollars <= 0:
                continue
            size = risk_dollars / stop_distance
            if candidate.side == "long":
                gross = (candidate.exit_price - candidate.entry_price) * size
            else:
                gross = (candidate.entry_price - candidate.exit_price) * size
            fees = (self.fee_rate_per_side + self.slippage_per_side) * (
                candidate.entry_price + candidate.exit_price
            ) * size
            net = gross - fees
            equity += net
            trades.append(
                ExecutedTrade(
                    candidate=candidate,
                    size=size,
                    risk_dollars=risk_dollars,
                    pnl_gross=gross,
                    fees_paid=fees,
                    pnl_net=net,
                    equity_after=equity,
                )
            )
            busy_until = candidate.exit_time

        return trades

    # ------------------------------------------------------------------
    # Reporting (spec §C)
    # ------------------------------------------------------------------
    def _summarise_setup(
        self,
        setup: SetupDefinition,
        candidates: List[CandidateSignal],
        trades: List[ExecutedTrade],
        is_boundary: datetime,
    ) -> Dict[str, Any]:
        vetoed = [c for c in candidates if c.veto_reasons]
        accepted = [c for c in candidates if not c.veto_reasons]

        by_reason: Dict[str, int] = {}
        for candidate in vetoed:
            for reason in candidate.veto_reasons:
                by_reason[reason] = by_reason.get(reason, 0) + 1

        window_comparison = {}
        for window in VETO_WINDOWS_COMPARED:
            w_accepted = [c for c in candidates if not c.vetoed_by_window.get(window, False)]
            w_vetoed = [c for c in candidates if c.vetoed_by_window.get(window, False)]
            window_comparison[str(window)] = {
                "accepted_n": len(w_accepted),
                "accepted_expectancy_R": self._mean_r(w_accepted),
                "vetoed_n": len(w_vetoed),
                "vetoed_expectancy_R": self._mean_r(w_vetoed),
            }

        grades: Dict[str, Any] = {}
        for grade in ("A", "B"):
            graded = [t for t in trades if t.candidate.adx_turn_grade == grade]
            grades[grade] = {
                "n_trades": len(graded),
                "expectancy_R": self._mean_r([t.candidate for t in graded]),
                "win_rate": self._win_rate([t.candidate for t in graded]),
            }

        is_trades = [t for t in trades if t.candidate.entry_time < is_boundary]
        oos_trades = [t for t in trades if t.candidate.entry_time >= is_boundary]

        return {
            "rule_version": setup.rule_version,
            "setup_id": setup.setup_id,
            "side": setup.side,
            "timeframes": list(setup.timeframes()),
            "candidates": len(candidates),
            "full": self._metrics_block(trades),
            "in_sample": self._metrics_block(is_trades),
            "out_of_sample": self._metrics_block(oos_trades),
            "vetoed_signals": {
                "count": len(vetoed),
                "by_reason": by_reason,
                "counterfactual_expectancy_R": self._mean_r(vetoed),
                "accepted_expectancy_R": self._mean_r(accepted),
                "window_comparison": window_comparison,
            },
            "adx_turn_grades": grades,
            "trades": [self._serialise_trade(t) for t in trades],
        }

    def _metrics_block(self, trades: List[ExecutedTrade]) -> Dict[str, Any]:
        n = len(trades)
        r_values = [t.pnl_net / t.risk_dollars for t in trades]
        wins = [r for r in r_values if r > 0]
        losses = [r for r in r_values if r <= 0]
        win_rate = len(wins) / n if n else 0.0
        expectancy = sum(r_values) / n if n else 0.0
        avg_win = sum(wins) / len(wins) if wins else 0.0
        avg_loss = sum(losses) / len(losses) if losses else 0.0
        gross_wins = sum(t.pnl_net for t in trades if t.pnl_net > 0)
        gross_losses = abs(sum(t.pnl_net for t in trades if t.pnl_net <= 0))
        if gross_losses > 0:
            profit_factor: float = round(gross_wins / gross_losses, 3)
        else:
            profit_factor = float("inf") if gross_wins > 0 else 0.0

        # Max drawdown over the trade-close equity sequence, re-based at the
        # block's first trade (trade-level, not bar-level — implementation
        # decision, documented for the gate report).
        max_dd = 0.0
        if trades:
            start_equity = trades[0].equity_after - trades[0].pnl_net
            peak = start_equity
            equity = start_equity
            for trade in trades:
                equity += trade.pnl_net
                peak = max(peak, equity)
                if peak > 0:
                    max_dd = max(max_dd, (peak - equity) / peak * 100.0)

        avg_duration = sum(t.candidate.bars_held for t in trades) / n if n else 0.0

        return {
            "n_trades": n,
            "win_rate": round(win_rate, 4),
            "expectancy_R": round(expectancy, 4),
            "avg_win_R": round(avg_win, 3),
            "avg_loss_R": round(avg_loss, 3),
            "profit_factor": profit_factor,
            "max_drawdown_pct": round(max_dd, 2),
            "avg_trade_duration_bars": round(avg_duration, 2),
        }

    @staticmethod
    def _mean_r(candidates: Sequence[CandidateSignal]) -> Optional[float]:
        if not candidates:
            return None
        return round(sum(c.r_net for c in candidates) / len(candidates), 4)

    @staticmethod
    def _win_rate(candidates: Sequence[CandidateSignal]) -> Optional[float]:
        if not candidates:
            return None
        return round(sum(1 for c in candidates if c.r_net > 0) / len(candidates), 4)

    @staticmethod
    def _serialise_trade(trade: ExecutedTrade) -> Dict[str, Any]:
        c = trade.candidate
        return {
            "entry_time": c.entry_time.isoformat(),
            "exit_time": c.exit_time.isoformat() if c.exit_time else None,
            "side": c.side,
            "entry_price": round(c.entry_price, 8),
            "exit_price": round(c.exit_price, 8),
            "stop_price": round(c.stop_price, 8),
            "target_price": round(c.target_price, 8),
            "exit_reason": c.exit_reason,
            "bars_held": c.bars_held,
            "r_net": round(c.r_net, 4),
            "pnl_net": round(trade.pnl_net, 2),
            "fees_paid": round(trade.fees_paid, 2),
            "adx_turn_grade": c.adx_turn_grade,
            "support": c.support,
        }

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------
    def _load_enriched_frame(self, timeframe: str) -> pd.DataFrame:
        """Paginated OHLCV (closed candles only) + indicator columns."""
        duration_ms = TIMEFRAME_SECONDS[timeframe] * 1000
        since = self.start - timedelta(milliseconds=duration_ms * self.warmup_bars)
        raw = self._fetch_paginated(timeframe, since)
        return self.enrich(raw)

    @staticmethod
    def enrich(df: pd.DataFrame) -> pd.DataFrame:
        """Compute every indicator column once over the full (causal) series."""
        service = IndicatorsService(df)
        service.calculate_all()
        return service.df

    def _fetch_paginated(self, timeframe: str, since_dt: datetime) -> pd.DataFrame:
        exchange = MarketDataService(exchange_name=self.exchange).exchange
        duration_ms = TIMEFRAME_SECONDS[timeframe] * 1000
        since_ms = int(since_dt.timestamp() * 1000)
        end_ms = int(self.end.timestamp() * 1000)
        limit = 1000
        rows: List[List[Any]] = []
        cursor = since_ms

        while cursor < end_ms:
            batch = exchange.fetch_ohlcv(
                symbol=self.symbol, timeframe=timeframe, since=cursor, limit=limit
            )
            if not batch:
                break
            rows.extend(batch)
            last_ts = batch[-1][0]
            next_cursor = last_ts + duration_ms
            if next_cursor <= cursor:
                break
            cursor = next_cursor
            if len(batch) < limit:
                break

        if not rows:
            raise ValueError(f"No OHLCV data returned for {self.symbol} {timeframe}")

        df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df = df.drop_duplicates(subset="timestamp").sort_values("timestamp")
        df.set_index("datetime", inplace=True)
        df = df[df.index <= self.end]

        # Closed candles only (spec §0.1): drop the forming last row.
        now_ms = time.time() * 1000.0
        if len(df) and int(df["timestamp"].iloc[-1]) + duration_ms > now_ms:
            df = df.iloc[:-1]
        return df

    @staticmethod
    def _ensure_utc(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
