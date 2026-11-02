from typing import Dict, Any, Optional

import numpy as np
import pandas as pd
import pandas_ta_classic as ta

from .bbwp_owner import bbwp_owner_series
from .koncorde import koncorde_series
from .trend_speed import trend_speed_analyzer


class IndicatorsService:
    """Service that computes technical indicators on a price DataFrame.

    Columns are added to the internal DataFrame and a dict with the latest
    (last candle) values is returned to the caller.
    """

    #: Which series the `bbwp` column/key carries (see `_calc_bbwp`):
    #: "tv" = the owner's TradingView BBWP (The_Caretaker, 13/256/5);
    #: "legacy" = the pre-2026-11-01 home-grown percentile (20/2, 252).
    BBWP_DEFINITIONS = ("tv", "legacy")

    def __init__(self, df: pd.DataFrame, *, bbwp_lookback: int = 252, bbwp_definition: str = "tv"):
        # Work on a copy to avoid mutating the caller's DataFrame.
        self.df = df.copy()
        self.bbwp_lookback = bbwp_lookback
        if bbwp_definition not in self.BBWP_DEFINITIONS:
            raise ValueError(f"Unknown bbwp_definition: {bbwp_definition!r} (use one of {self.BBWP_DEFINITIONS})")
        self.bbwp_definition = bbwp_definition

    @staticmethod
    def _safe_last(series: pd.Series, default: float = 0.0) -> float:
        """Return the last non-NaN value of a Series, or `default` if empty."""
        valid = series.dropna()
        if valid.empty:
            return default
        return float(valid.iloc[-1])

    # ---------------------------------------------------------------------
    # Main entrypoint
    # ---------------------------------------------------------------------
    def calculate_all(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {}

        self._calc_rsi(result)
        self._calc_adx(result)
        self._calc_bbwp(result)
        self._calc_bbwp_owner(result)
        self._calc_ao(result)
        self._calc_moving_averages(result)
        self._calc_konkorde(result)
        self._calc_momentum_indicators(result)
        self._calc_volatility_indicators(result)
        self._calc_trend_speed(result)
        self._calc_ml_rsi(result)

        return result

    def calculate_impulse(self, *, ml_rsi: bool = True) -> Dict[str, Any]:
        """Compute ONLY what the impulse engines read (cheaper than `calculate_all`).

        `impulse_service._derive` / `impulse_sequential.derive_sequential` consume
        `rsi14`, `adx14` / `plus_di` / `minus_di`, `bbwp` (the selected definition),
        `ao`, the `konkorde_*` lines, `macd` / `macd_signal`, `atr14` and
        `ml_rsi_regime`. Every column computed here is the SAME series
        `calculate_all` produces (same functions, same parameters, same order);
        what is skipped — the legacy BBWP percentile, the moving averages, the
        Trend Speed Analyzer and the `bbwp_owner` aliases — is never read by
        those engines. `ml_rsi=False` leaves the ML RSI columns to the caller
        (the shadow runner serves them from an incremental cache).
        """
        result: Dict[str, Any] = {}
        self._calc_rsi(result)
        self._calc_adx(result)
        self._calc_bbwp(result, legacy=False)
        self._calc_ao(result)
        self._calc_konkorde(result)
        self._calc_momentum_indicators(result)
        self._calc_volatility_indicators(result)
        if ml_rsi:
            self._calc_ml_rsi(result)
        return result

    def calculate_konkorde(self) -> Dict[str, Any]:
        """Compute ONLY the Konkorde block (cheaper than `calculate_all`).

        The full series stay on `self.df` as the `konkorde_azul`,
        `konkorde_verde`, `konkorde_marron` and `konkorde_media` columns;
        the returned dict carries the last-candle values (same keys as
        `calculate_all`).
        """
        result: Dict[str, Any] = {}
        self._calc_konkorde(result)
        return result

    def calculate_oscillators(self) -> Dict[str, Any]:
        """Compute ONLY the ADX / BBWP / AO oscillators (cheaper than
        `calculate_all`).

        The full series stay on `self.df` as the `adx14`, `plus_di`,
        `minus_di`, `bbwp` and `ao` columns — plus the TradingView-parity
        variants `bbwp_owner`, `bbwp_owner_ma5`, `ao_diff`, `ao_color` and
        the `tsa_*` Trend Speed Analyzer columns; the returned dict carries
        the last-candle values (same keys as `calculate_all`). Used by the
        chart service to ship per-candle oscillator panels alongside
        Konkorde.
        """
        result: Dict[str, Any] = {}
        self._calc_adx(result)
        self._calc_bbwp(result)
        self._calc_bbwp_owner(result)
        self._calc_ao(result)
        self._calc_trend_speed(result)
        return result

    # ------------------------------------------------------------------
    # Individual indicators (private)
    # ------------------------------------------------------------------
    def _calc_rsi(self, result: Dict[str, Any]):
        rsi = ta.rsi(self.df["close"], length=14)
        if rsi is None:
            rsi = pd.Series(np.nan, index=self.df.index)
        self.df["rsi14"] = rsi
        result["rsi14"] = self._safe_last(self.df["rsi14"])

    def _calc_ml_rsi(self, result: Dict[str, Any]):
        """ML RSI [BackQuant] regime filter (impulsos-v2 round 3, owner decision 4).

        Additive: NEW keys only (`ml_rsi`, `ml_rsi_upper`, `ml_rsi_lower`,
        `ml_rsi_regime`, `ml_rsi_points`); the legacy payload is untouched.
        Thresholds are causal (only candles <= the current one) over the last
        3000 values available: with `/v1/metrics/get` default `limit=500` the
        thresholds are fitted on ~480 points, so they will not match a
        TradingView chart with 3000 bars of history; `ml_rsi_points` says how
        many values fed them. See `ml_rsi.py` for what TV really plots.
        """
        from .ml_rsi import MlRsiParams, ml_rsi_frame

        frame = ml_rsi_frame(self.df["close"], MlRsiParams(), mode="causal")
        for col in ("ml_rsi", "ml_rsi_upper", "ml_rsi_lower"):
            self.df[col] = frame[col].to_numpy()
            result[col] = self._safe_last(self.df[col])
        self.df["ml_rsi_regime"] = frame["ml_rsi_regime"].to_numpy(dtype=object)
        regimes = [r for r in frame["ml_rsi_regime"].tolist() if r is not None]
        result["ml_rsi_regime"] = regimes[-1] if regimes else "unknown"
        result["ml_rsi_points"] = int(np.isfinite(frame["ml_rsi"].to_numpy(dtype=float)).sum())

    def _calc_adx(self, result: Dict[str, Any]):
        """ADX(14) plus directional indicators (+DI / -DI).

        Without +DI/-DI an ADX > 25 reading is direction-agnostic, so we
        expose them so downstream consumers (RulesService) can decide
        whether the trend is bullish or bearish.
        """
        try:
            adx = ta.adx(self.df["high"], self.df["low"], self.df["close"], length=14)
        except Exception:
            adx = None
        if adx is not None and "ADX_14" in adx.columns:
            self.df["adx14"] = adx["ADX_14"]
            self.df["plus_di"] = adx["DMP_14"]
            self.df["minus_di"] = adx["DMN_14"]
        else:
            nan_series = pd.Series(np.nan, index=self.df.index)
            self.df["adx14"] = nan_series
            self.df["plus_di"] = nan_series
            self.df["minus_di"] = nan_series
        result["adx14"] = self._safe_last(self.df["adx14"])
        result["plus_di"] = self._safe_last(self.df["plus_di"])
        result["minus_di"] = self._safe_last(self.df["minus_di"])

    def _calc_bbwp(self, result: Dict[str, Any], *, legacy: bool = True):
        """Bollinger Band Width (BBW) and Bollinger Band Width Percentile (BBWP).

        `legacy=False` (only `calculate_impulse`) skips the `bbwp_legacy`
        series — a per-bar `rank` over 252 rows that dominates the cost — and
        is only allowed with the "tv" definition, where nothing reads it.

        Two definitions are always computed and exposed:

        * `bbwp_tv` — the owner's TradingView reading: exact port of
          The_Caretaker's `f_bbwp` with the owner's chart settings (close,
          basis SMA 13, lookback 256, SMA 5 over the BBWP -> `bbwp_ma5`; see
          `bbwp_owner.py`). `bbw13` is its raw width in % (2*stdev/basis).
        * `bbwp_legacy` — the pre-2026-11-01 home-grown variant: BBands 20/2
          width `bbw` (%), pct-rank INCLUDING the current bar over a
          min_periods=1 rolling `bbwp_lookback` (252) window.

        `bbwp` (and `bbwp_ma4`, its 4-bar SMA kept for backwards compat)
        carries the one selected by `bbwp_definition`:

        * default "tv": `/v1/metrics`, `/v1/charts`, `/v1/movements` and the
          legacy `RulesService` read what the owner sees. The audit of
          2026-11-01 found the legacy series at 85-92 on 4h BTC while the
          chart said 15-19 — the "huge difference" the owner reported.
        * "legacy": the VERSIONED rule packs (setups v0.1.0, monitors
          v0.2.x, their backtests) keep the series their real-candle goldens
          were pinned on (spec §0.4: a rule input change needs a
          `rule_version` bump — the C1-G1 golden flips its 1h BBWP component
          on the TV series). See `setup_service.RULE_PACK_BBWP_DEFINITION`.
        """
        if not legacy and self.bbwp_definition != "tv":
            raise ValueError("legacy=False needs bbwp_definition='tv' (the legacy series would be the selected one)")
        bb = ta.bbands(self.df["close"], length=20, std=2)
        bbw = (bb["BBU_20_2.0"] - bb["BBL_20_2.0"]) / bb["BBM_20_2.0"] * 100
        self.df["bbw"] = bbw
        if legacy:
            self.df["bbwp_legacy"] = bbw.rolling(self.bbwp_lookback, min_periods=1).apply(
                lambda x: x.rank(pct=True).iloc[-1] * 100,
                raw=False,
            )

        owner = bbwp_owner_series(self.df["close"])
        self.df["bbw13"] = owner["bbw"] * 100.0
        self.df["bbwp_tv"] = owner["bbwp"]
        self.df["bbwp_ma5"] = owner["bbwp_ma"]

        selected = "bbwp_tv" if self.bbwp_definition == "tv" else "bbwp_legacy"
        self.df["bbwp"] = self.df[selected]
        self.df["bbwp_ma4"] = self.df["bbwp"].rolling(4).mean()

        result["bbwp_definition"] = self.bbwp_definition
        result["bbw"] = self._safe_last(self.df["bbw"])
        result["bbw13"] = self._safe_last(self.df["bbw13"])
        result["bbwp"] = self._safe_last(self.df["bbwp"])
        result["bbwp_ma4"] = self._safe_last(self.df["bbwp_ma4"])
        result["bbwp_ma5"] = self._safe_last(self.df["bbwp_ma5"])
        result["bbwp_tv"] = self._safe_last(self.df["bbwp_tv"])
        if legacy:
            result["bbwp_legacy"] = self._safe_last(self.df["bbwp_legacy"])

    def _calc_bbwp_owner(self, result: Dict[str, Any]):
        """`bbwp_owner` / `bbwp_owner_ma5`: ALIASES of `bbwp_tv` / `bbwp_ma5`
        (the 2026-07-16 Q19 names) so the dashboard panels and the recorded
        comparisons keep working unchanged."""
        if "bbwp_tv" not in self.df.columns:
            self._calc_bbwp(result)
        self.df["bbwp_owner"] = self.df["bbwp_tv"]
        self.df["bbwp_owner_ma5"] = self.df["bbwp_ma5"]
        result["bbwp_owner"] = self._safe_last(self.df["bbwp_owner"])
        result["bbwp_owner_ma5"] = self._safe_last(self.df["bbwp_owner_ma5"])

    def _calc_ao(self, result: Dict[str, Any]):
        """Awesome Oscillator + the exact TradingView colour reading.

        `ta.ao` already matches the Pine built-in (`sma(hl2,5)-sma(hl2,34)`,
        verified by `tests/test_ao_parity.py`). The owner reads the COLOUR
        of the AO columns, which is the sign of `diff = ao - ao[1]` with
        ties painted RED (Pine: `diff <= 0 ? red : green`) — so `ao_diff`
        and `ao_color` are exposed alongside the raw value. A colour change
        is a cross of `diff` with zero (Pine crossover/crossunder).
        """
        ao = ta.ao(self.df["high"], self.df["low"])
        if ao is None:  # pandas-ta returns None when the series is < 34 bars
            ao = pd.Series(np.nan, index=self.df.index)
        self.df["ao"] = ao
        last_ao = self.df["ao"].dropna().iloc[-1] if self.df["ao"].dropna().size else 0.0
        result["ao"] = float(last_ao)

        ao_diff = self.df["ao"].diff()
        self.df["ao_diff"] = ao_diff
        color = pd.Series(
            np.where(ao_diff > 0, "green", "red"), index=self.df.index, dtype="object"
        )
        color[ao_diff.isna()] = None
        self.df["ao_color"] = color
        result["ao_diff"] = self._safe_last(ao_diff)
        result["ao_color"] = self._last_color(color)
        result["ao_color_change"] = self._ao_color_change(ao_diff)

    @staticmethod
    def _last_color(color: pd.Series) -> Optional[str]:
        valid = color.dropna()
        return str(valid.iloc[-1]) if valid.size else None

    @staticmethod
    def _ao_color_change(ao_diff: pd.Series) -> Optional[str]:
        """Pine `ta.crossover/crossunder(diff, 0)` on the last closed candle."""
        clean = ao_diff.dropna()
        if len(clean) < 2:
            return None
        current, previous = float(clean.iloc[-1]), float(clean.iloc[-2])
        if current > 0 and previous <= 0:
            return "to_green"
        if current < 0 and previous >= 0:
            return "to_red"
        return None

    def _calc_moving_averages(self, result: Dict[str, Any]):
        for period in [50, 200]:
            sma_name = f"sma{period}"
            ema_name = f"ema{period}"
            self.df[sma_name] = ta.sma(self.df["close"], length=period)
            self.df[ema_name] = ta.ema(self.df["close"], length=period)
            last_sma = self.df[sma_name].dropna().iloc[-1] if self.df[sma_name].dropna().size else 0.0
            last_ema = self.df[ema_name].dropna().iloc[-1] if self.df[ema_name].dropna().size else 0.0
            result[sma_name] = float(last_sma)
            result[ema_name] = float(last_ema)

    def _calc_konkorde(self, result: Dict[str, Any]):
        """Koncorde by Blai5 — bar-exact port of the public Pine script.

        Formula and Pine semantics live in `koncorde.py`. Four lines:
            * marron (brown)  -> trend: (RSI + MFI + BollOsc + Stoch/3) / 2
                                 over ohlc4; NOT centred on zero (0-100
                                 inputs), ~+55 in a flat market like the
                                 TradingView plot.
            * verde  (green)  -> weak hands: marron + PVI oscillator (the
                                 area the owner reads as "yellow").
            * azul   (blue)   -> strong hands: NVI oscillator.
            * media  (red)    -> EMA(15) of marron; Blai5's signal is the
                                 marron/media cross.

        History: until 2026-11-01 this method computed a different indicator
        (EMA(255) of PVI/NVI, azul=PVI, no stochastic, RSI on close, half
        Bollinger divisor, RSI/MFI "re-centred" by -50, see decisions.md
        D6/D18). It disagreed with the owner's chart by sign on 4h and even
        between exchanges for the same market (binance -128 vs bitget +32).

        `konkorde_value` stays as the DEPRECATED alias of `konkorde_marron`;
        `RulesService` now reads it against `konkorde_media`.
        """
        lines = koncorde_series(self.df)

        self.df["konkorde_azul"] = lines["azul"]
        self.df["konkorde_verde"] = lines["verde"]
        self.df["konkorde_marron"] = lines["marron"]
        self.df["konkorde_media"] = lines["media"]

        last_azul = self._safe_last(lines["azul"])
        last_verde = self._safe_last(lines["verde"])
        last_marron = self._safe_last(lines["marron"])
        last_media = self._safe_last(lines["media"])

        result["konkorde_azul"] = last_azul
        result["konkorde_verde"] = last_verde
        result["konkorde_marron"] = last_marron
        result["konkorde_media"] = last_media
        # Backwards-compatible alias (DEPRECATED): equals the marron line.
        result["konkorde_value"] = last_marron

        result["konkorde_signal"] = self._classify_konkorde(last_azul, last_verde, last_marron, last_media)

    @staticmethod
    def _classify_konkorde(azul: float, verde: float, marron: float, media: float) -> str:
        """Blai5 reading: trend = marron vs its media; strong hands = azul sign.

        `marron > 0` is NOT a usable condition on the real indicator (it is
        almost always true), so the trend side is the marron/media relation
        and the strength qualifier is whether strong hands (azul) agree.
        """
        if marron > media:
            return "bullish_strong" if azul > 0 else "bullish_weak"
        if marron < media:
            return "bearish_strong" if azul < 0 else "bearish_weak"
        return "neutral"

    def _calc_momentum_indicators(self, result: Dict[str, Any]):
        """Additional momentum indicators that complement the main set."""
        # MACD — pandas_ta returns None when the series is too short for the
        # default 26-period EMA, fall back to NaN values rather than crashing.
        try:
            macd = ta.macd(self.df["close"])
        except Exception:
            macd = None
        if macd is not None and "MACD_12_26_9" in macd.columns:
            self.df["macd"] = macd["MACD_12_26_9"]
            self.df["macd_signal"] = macd["MACDs_12_26_9"]
            self.df["macd_histogram"] = macd["MACDh_12_26_9"]
            result["macd"] = self._safe_last(self.df["macd"])
            result["macd_signal"] = self._safe_last(self.df["macd_signal"])
            result["macd_histogram"] = self._safe_last(self.df["macd_histogram"])
        else:
            result["macd"] = 0.0
            result["macd_signal"] = 0.0
            result["macd_histogram"] = 0.0

        # Stochastic RSI
        try:
            stoch_rsi = ta.stochrsi(self.df["close"], length=14)
        except Exception:
            stoch_rsi = None
        if stoch_rsi is not None and "STOCHRSIk_14_14_3_3" in stoch_rsi.columns:
            result["stoch_rsi_k"] = self._safe_last(stoch_rsi["STOCHRSIk_14_14_3_3"])
            result["stoch_rsi_d"] = self._safe_last(stoch_rsi["STOCHRSId_14_14_3_3"])
        else:
            result["stoch_rsi_k"] = 0.0
            result["stoch_rsi_d"] = 0.0

    def _calc_volatility_indicators(self, result: Dict[str, Any]):
        """Volatility indicators that complement BBW/BBWP."""
        # Average True Range (ATR)
        try:
            atr = ta.atr(self.df["high"], self.df["low"], self.df["close"], length=14)
        except Exception:
            atr = None
        if atr is None:
            atr = pd.Series(np.nan, index=self.df.index)
        self.df["atr14"] = atr
        result["atr"] = self._safe_last(atr)

        # Realised volatility (rolling stdev of returns) expressed in %.
        returns = self.df["close"].pct_change()
        volatility = returns.rolling(20).std() * 100
        result["volatility_20"] = self._safe_last(volatility)

    def _calc_trend_speed(self, result: Dict[str, Any]):
        """Trend Speed Analyzer (Zeiierman) — TradingView parity port.

        Bar-exact port (see `trend_speed.py`, CC BY-NC-SA 4.0 attribution
        there). Series land on `self.df` as `tsa_dyn_ema`, `tsa_speed`,
        `tsa_trend_speed` (the HMA-5 histogram the owner sees) and
        `tsa_wave_dir`; the wave-table stats land in the result dict.
        Comparison-only for now: no rule consumes these outputs.
        """
        tsa = trend_speed_analyzer(self.df["open"], self.df["close"])
        self.df["tsa_dyn_ema"] = tsa.frame["dyn_ema"]
        self.df["tsa_speed"] = tsa.frame["speed"]
        self.df["tsa_trend_speed"] = tsa.frame["trend_speed"]
        self.df["tsa_wave_dir"] = tsa.frame["wave_dir"]
        result["trend_speed"] = self._safe_last(self.df["tsa_trend_speed"])
        result["trend_speed_raw"] = self._safe_last(self.df["tsa_speed"])
        result["trend_speed_dyn_ema"] = self._safe_last(self.df["tsa_dyn_ema"])
        result["trend_speed_stats"] = tsa.stats
