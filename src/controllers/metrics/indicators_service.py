from typing import Dict, Any

import pandas as pd
import pandas_ta as ta


class IndicatorsService:
    """Servicio para calcular indicadores técnicos sobre un DataFrame de precios.
    Se agregan columnas al DataFrame interno y se devuelve un diccionario con los
    valores actuales (última vela)."""

    def __init__(self, df: pd.DataFrame):
        # Se trabaja sobre una copia para no modificar el DataFrame original
        self.df = df.copy()

    # ---------------------------------------------------------------------
    # Cálculo principal
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
    # Indicadores individuales (privados)
    # ------------------------------------------------------------------
    def _calc_rsi(self, result: Dict[str, Any]):
        self.df["rsi14"] = ta.rsi(self.df["close"], length=14)
        result["rsi14"] = float(self.df["rsi14"].iloc[-1])

    def _calc_adx(self, result: Dict[str, Any]):
        adx = ta.adx(self.df["high"], self.df["low"], self.df["close"], length=14)
        self.df["adx14"] = adx["ADX_14"]
        result["adx14"] = float(self.df["adx14"].iloc[-1])

    def _calc_bbwp(self, result: Dict[str, Any]):
        """BBWP → Bollinger Band Width Percentage.
        Fórmula: (Upper - Lower) / Middle * 100.
        Además se suaviza con una media móvil de 4 periodos para reducir ruido.
        """
        bb = ta.bbands(self.df["close"], length=20, std=2)
        width = (bb["BBU_20_2.0"] - bb["BBL_20_2.0"]) / bb["BBM_20_2.0"] * 100
        self.df["bbwp"] = width
        self.df["bbwp_ma4"] = width.rolling(4).mean()

        result["bbwp"] = float(width.iloc[-1])
        result["bbwp_ma4"] = float(self.df["bbwp_ma4"].iloc[-1])

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
        """Versión simplificada de Konkorde:
        OBV y su EMA de 20 periodos. La señal es el valor residual (OBV - EMA).
        Si es positivo → presión compradora (bullish)."""
        self.df["obv"] = ta.obv(self.df["close"], self.df["volume"])
        self.df["obv_ema20"] = ta.ema(self.df["obv"], length=20)
        self.df["konkorde_val"] = self.df["obv"] - self.df["obv_ema20"]

        result["konkorde_value"] = float(self.df["konkorde_val"].iloc[-1])
        result["konkorde_signal"] = "bullish" if result["konkorde_value"] > 0 else "bearish"

    def _calc_momentum_indicators(self, result: Dict[str, Any]):
        """Indicadores de momentum adicionales para mejorar las señales."""
        # MACD
        macd = ta.macd(self.df["close"])
        self.df["macd"] = macd["MACD_12_26_9"]
        self.df["macd_signal"] = macd["MACDs_12_26_9"]
        self.df["macd_histogram"] = macd["MACDh_12_26_9"]
        
        result["macd"] = float(self.df["macd"].iloc[-1]) if not self.df["macd"].isna().iloc[-1] else 0.0
        result["macd_signal"] = float(self.df["macd_signal"].iloc[-1]) if not self.df["macd_signal"].isna().iloc[-1] else 0.0
        result["macd_histogram"] = float(self.df["macd_histogram"].iloc[-1]) if not self.df["macd_histogram"].isna().iloc[-1] else 0.0
        
        # Stochastic RSI
        stoch_rsi = ta.stochrsi(self.df["close"], length=14)
        result["stoch_rsi_k"] = float(stoch_rsi["STOCHRSIk_14_14_3_3"].iloc[-1]) if "STOCHRSIk_14_14_3_3" in stoch_rsi.columns else 0.0
        result["stoch_rsi_d"] = float(stoch_rsi["STOCHRSId_14_14_3_3"].iloc[-1]) if "STOCHRSId_14_14_3_3" in stoch_rsi.columns else 0.0

    def _calc_volatility_indicators(self, result: Dict[str, Any]):
        """Indicadores de volatilidad para complementar BBWP."""
        # Average True Range (ATR)
        atr = ta.atr(self.df["high"], self.df["low"], self.df["close"], length=14)
        result["atr"] = float(atr.iloc[-1]) if not atr.isna().iloc[-1] else 0.0
        
        # Volatilidad realizada (desviación estándar de returns)
        returns = self.df["close"].pct_change()
        volatility = returns.rolling(20).std() * 100  # En porcentaje
        result["volatility_20"] = float(volatility.iloc[-1]) if not volatility.isna().iloc[-1] else 0.0
