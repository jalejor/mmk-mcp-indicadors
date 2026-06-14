from typing import Dict, Any

import numpy as np
import pandas as pd
import pandas_ta_classic as ta


class IndicatorsService:
    """Service that computes technical indicators on a price DataFrame.

    Columns are added to the internal DataFrame and a dict with the latest
    (last candle) values is returned to the caller.
    """

    def __init__(self, df: pd.DataFrame, *, bbwp_lookback: int = 252):
        # Work on a copy to avoid mutating the caller's DataFrame.
        self.df = df.copy()
        self.bbwp_lookback = bbwp_lookback

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
        self._calc_ao(result)
        self._calc_moving_averages(result)
        self._calc_konkorde(result)
        self._calc_momentum_indicators(result)
        self._calc_volatility_indicators(result)

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

    def _calc_bbwp(self, result: Dict[str, Any]):
        """Bollinger Band Width (BBW) and Bollinger Band Width Percentile (BBWP).

        BBW is the raw width: (Upper - Lower) / Middle * 100.
        BBWP ranks each BBW reading against the previous `bbwp_lookback`
        bars and returns a 0-100 percentile. A reading near 100 means the
        bands are wider than they have been almost all of the lookback
        window (volatility expansion); near 0 means historic compression.
        Source: John A. Bollinger via the public TradingView indicator
        "Bollinger Band Width Percentile".
        """
        bb = ta.bbands(self.df["close"], length=20, std=2)
        bbw = (bb["BBU_20_2.0"] - bb["BBL_20_2.0"]) / bb["BBM_20_2.0"] * 100
        self.df["bbw"] = bbw
        # Percentile rank of the current BBW value within the rolling window.
        self.df["bbwp"] = bbw.rolling(self.bbwp_lookback, min_periods=1).apply(
            lambda x: x.rank(pct=True).iloc[-1] * 100,
            raw=False,
        )
        # Smoothed BBWP for visual confirmation (kept for backwards compat).
        self.df["bbwp_ma4"] = self.df["bbwp"].rolling(4).mean()

        result["bbw"] = self._safe_last(self.df["bbw"])
        result["bbwp"] = self._safe_last(self.df["bbwp"])
        result["bbwp_ma4"] = self._safe_last(self.df["bbwp_ma4"])

    def _calc_ao(self, result: Dict[str, Any]):
        self.df["ao"] = ta.ao(self.df["high"], self.df["low"])
        last_ao = self.df["ao"].dropna().iloc[-1] if self.df["ao"].dropna().size else 0.0
        result["ao"] = float(last_ao)

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
        """Konkorde indicator by Blai5.

        Reference: public Pine Script "Konkorde by Blai5" on TradingView.
        Three lines are produced:
            * azul   (blue)   -> retail / weak hands flow (PVI oscillator).
            * verde  (green)  -> trend / strong hands flow.
            * marron (brown)  -> net strong hands position.

        Formula:
        1. tprice = OHLC4 typical price.
        2. PVI / NVI: cumulative volume-weighted price change indices,
           updated only when current volume rises (PVI) or falls (NVI)
           against the previous bar. Both initialised to 1000.
        3. For PVI and NVI compute their EMA(255), then the rolling 90-bar
           max/min of that EMA; the oscillator is
               OscX = (X - EMA_X) * 100 / (max90 - min90)
        4. MFI(14) over tprice, B1 = bollinger oscillator over tprice,
           RSI(14) over close.
        5. Lines (Blai5 keeps every component centred on zero so the three
           lines share the same axis and a reading of 0 means "neutral"):
               azul   = OscP
               verde  = ((MFI - 50) + B1 + OscP) / 3
               marron = ((RSI - 50) + (MFI - 50) + B1 + OscP - OscN) / 4

        WHY the `- 50`: RSI and MFI are 0-100 oscillators centred on 50,
        whereas B1/OscP/OscN are already centred on 0. Averaging the raw
        0-100 series with the 0-centred ones used to leave the brown line
        at ~+25 in a flat market, which the rules engine then read as a
        permanent `konkorde_buy` vote (weight 3.0). Subtracting the 50
        baseline re-centres the line so neutral markets score ~0, matching
        Blai5's canonical Pine where the brown line crosses zero to signal.

        DEPRECATED: `konkorde_value` is kept as an alias of
        `konkorde_marron` so existing consumers keep working.
        """
        df = self.df
        close = df["close"]
        high = df["high"]
        low = df["low"]
        open_ = df["open"]
        volume = df["volume"]

        tprice = (open_ + high + low + close) / 4.0

        # PVI and NVI -----------------------------------------------------
        prev_close = close.shift(1)
        prev_volume = volume.shift(1)
        change_ratio = (close - prev_close) / prev_close.replace(0, np.nan)

        pvi_factor = np.where(volume > prev_volume, 1.0 + change_ratio.fillna(0.0), 1.0)
        nvi_factor = np.where(volume < prev_volume, 1.0 + change_ratio.fillna(0.0), 1.0)
        pvi = pd.Series(pvi_factor, index=df.index).cumprod() * 1000.0
        nvi = pd.Series(nvi_factor, index=df.index).cumprod() * 1000.0

        # Oscillators -----------------------------------------------------
        # `ta.ema` returns None when the series is shorter than `length`.
        # Fall back to pandas' own EMA so the calculation never crashes
        # on short windows (very common during warmup or unit tests).
        ema_pvi = ta.ema(pvi, length=255)
        if ema_pvi is None:
            ema_pvi = pvi.ewm(span=min(255, max(2, len(pvi))), adjust=False).mean()
        ema_nvi = ta.ema(nvi, length=255)
        if ema_nvi is None:
            ema_nvi = nvi.ewm(span=min(255, max(2, len(nvi))), adjust=False).mean()
        max90_p = ema_pvi.rolling(90, min_periods=1).max()
        min90_p = ema_pvi.rolling(90, min_periods=1).min()
        max90_n = ema_nvi.rolling(90, min_periods=1).max()
        min90_n = ema_nvi.rolling(90, min_periods=1).min()
        # Use the wider span of either oscillator to avoid div-by-zero,
        # mirroring Blai5's original Pine that uses the same denominator.
        denom_p = (max90_p - min90_p).replace(0, np.nan)
        denom_n = (max90_n - min90_n).replace(0, np.nan)
        osc_p = (pvi - ema_pvi) * 100.0 / denom_p
        osc_n = (nvi - ema_nvi) * 100.0 / denom_n

        # Money Flow Index over tprice -----------------------------------
        # pandas_ta.mfi expects high/low/close, but Blai5 uses tprice as the
        # price series. We approximate using high=low=close=tprice.
        try:
            mfi = ta.mfi(tprice, tprice, tprice, volume, length=14)
        except Exception:
            mfi = pd.Series(np.nan, index=df.index)
        if mfi is None:
            mfi = pd.Series(np.nan, index=df.index)

        # Bollinger oscillator over tprice -------------------------------
        sma25 = tprice.rolling(25).mean()
        std25 = tprice.rolling(25).std(ddof=0)
        b1 = (tprice - sma25) / (2 * std25.replace(0, np.nan)) * 100.0

        rsi14 = ta.rsi(close, length=14)
        if rsi14 is None:
            rsi14 = pd.Series(np.nan, index=df.index)

        # Re-centre the 0-100 oscillators (RSI, MFI) on zero so they share
        # the same axis as the already 0-centred B1/OscP/OscN. Without this
        # the brown line floats at ~+25 in a neutral market (50/2) and the
        # rules engine reads `marron > 0` as a permanent buy vote.
        rsi_centered = rsi14 - 50.0
        mfi_centered = mfi - 50.0

        azul = osc_p
        verde = (mfi_centered + b1 + osc_p) / 3.0
        marron = (rsi_centered + mfi_centered + b1 + osc_p - osc_n) / 4.0

        df["konkorde_azul"] = azul
        df["konkorde_verde"] = verde
        df["konkorde_marron"] = marron

        last_azul = self._safe_last(azul)
        last_verde = self._safe_last(verde)
        last_marron = self._safe_last(marron)

        result["konkorde_azul"] = last_azul
        result["konkorde_verde"] = last_verde
        result["konkorde_marron"] = last_marron
        # Backwards-compatible alias (DEPRECATED): equals the marron line.
        result["konkorde_value"] = last_marron

        result["konkorde_signal"] = self._classify_konkorde(last_azul, last_verde, last_marron)

    @staticmethod
    def _classify_konkorde(azul: float, verde: float, marron: float) -> str:
        if marron > 0 and verde > azul:
            return "bullish_strong"
        if azul > marron and azul > 0:
            return "bullish_weak"
        if marron < 0 and verde < azul:
            return "bearish_strong"
        if azul < 0 and azul < marron:
            return "bearish_weak"
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
