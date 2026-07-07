from typing import Any, Dict, List
from os import getenv


class RulesService:
    """Evaluates trading rules (entry, exit, neutral) with configurable thresholds.

    Thresholds can be customised in three ways (highest priority wins):
    1. DEFAULT_THRESHOLDS.
    2. Global env vars, e.g. RSI_OVERBOUGHT.
    3. Per-symbol env vars, e.g. BTC_USDT_RSI_OVERSOLD.
    4. The `thresholds` constructor argument.

    Phase 4 additions:
    * Weighted voting per indicator family.  See `DEFAULT_WEIGHTS`.
    * Market-regime detection (compression / exhaustion / trending /
      ranging / transitional) that biases the weights and can suppress
      signals when the regime is too dangerous to act on.
    """

    DEFAULT_THRESHOLDS: Dict[str, float] = {
        "rsi_overbought": 70.0,
        "rsi_oversold": 30.0,
        "adx_trend": 25.0,
        "bbwp_high": 80.0,
        "bbwp_low": 20.0,
    }

    DEFAULT_WEIGHTS: Dict[str, float] = {
        "konkorde": 3.0,
        "ao": 2.0,
        "adx": 2.0,
        "macd": 1.5,
        "rsi": 1.0,
        "bbwp": 1.0,
        "stoch_rsi": 1.0,
        "ma_cross": 1.0,
        "volatility": 0.5,
    }

    # Maps every signal code emitted in `support_entry` / `support_exit` to
    # the indicator family used to look up its weight.
    _SIGNAL_FAMILY: Dict[str, str] = {
        "rsi_oversold": "rsi",
        "rsi_overbought": "rsi",
        "vol_low": "bbwp",
        "vol_high": "bbwp",
        "adx_trend": "adx",
        "adx_trend_bullish": "adx",
        "adx_trend_bearish": "adx",
        "konkorde_buy": "konkorde",
        "konkorde_sell": "konkorde",
        "ao_positive": "ao",
        "ao_negative": "ao",
        "ema50_gt_sma50": "ma_cross",
        "ema50_lt_sma50": "ma_cross",
        "macd_bullish": "macd",
        "macd_bearish": "macd",
        "stoch_rsi_oversold": "stoch_rsi",
        "stoch_rsi_overbought": "stoch_rsi",
        "low_volatility": "volatility",
    }

    def __init__(
        self,
        *,
        symbol: str,
        thresholds: Dict[str, float] | None = None,
        weights: Dict[str, float] | None = None,
    ):
        """`symbol` is expected as "BTC/USDT" so per-asset env overrides apply."""
        self.symbol = symbol.upper().replace("/", "_")

        # 1. Defaults
        th = self.DEFAULT_THRESHOLDS.copy()

        # 2. Global env overrides
        for key in th.keys():
            env_val = getenv(key.upper())
            if env_val is not None:
                th[key] = float(env_val)

        # 3. Per-symbol env overrides
        for key in th.keys():
            env_key = f"{self.symbol}_{key.upper()}"
            env_val = getenv(env_key)
            if env_val is not None:
                th[key] = float(env_val)

        # 4. Caller-provided overrides
        if thresholds:
            th.update(thresholds)

        self.thresholds = th

        # Weights: defaults -> env override (e.g. KONKORDE_WEIGHT=4.0) ->
        # explicit constructor override.
        w = self.DEFAULT_WEIGHTS.copy()
        for key in list(w.keys()):
            env_val = getenv(f"{key.upper()}_WEIGHT")
            if env_val is not None:
                w[key] = float(env_val)
        if weights:
            w.update(weights)
        self.weights = w

    # ------------------------------------------------------------
    # Regime detection
    # ------------------------------------------------------------
    def _detect_regime(self, indicators: Dict[str, Any]) -> str:
        bbwp = indicators.get("bbwp")
        adx = indicators.get("adx14")
        if bbwp is not None:
            if bbwp < self.thresholds["bbwp_low"]:
                return "compression"
            if bbwp > self.thresholds["bbwp_high"]:
                return "exhaustion"
        if adx is not None:
            if adx > self.thresholds["adx_trend"]:
                return "trending"
            if adx < 20.0:
                return "ranging"
        return "transitional"

    # ------------------------------------------------------------
    # Signal evaluation
    # ------------------------------------------------------------
    def evaluate(self, indicators: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate multiple indicators and return a structured trade plan."""
        th = self.thresholds
        entry_support: List[str] = []
        exit_support: List[str] = []

        rsi = indicators.get("rsi14")
        if rsi is not None:
            if rsi < th["rsi_oversold"]:
                entry_support.append("rsi_oversold")
            elif rsi > th["rsi_overbought"]:
                exit_support.append("rsi_overbought")

        bbwp = indicators.get("bbwp")
        if bbwp is not None:
            if bbwp < th["bbwp_low"]:
                entry_support.append("vol_low")
            elif bbwp > th["bbwp_high"]:
                exit_support.append("vol_high")

        adx = indicators.get("adx14")
        plus_di = indicators.get("plus_di")
        minus_di = indicators.get("minus_di")
        if adx is not None and plus_di is not None and minus_di is not None:
            if adx >= th["adx_trend"]:
                if plus_di > minus_di:
                    entry_support.append("adx_trend_bullish")
                elif minus_di > plus_di:
                    exit_support.append("adx_trend_bearish")
        elif adx is not None and adx >= th["adx_trend"]:
            entry_support.append("adx_trend")

        konkorde_val = indicators.get("konkorde_value")
        if konkorde_val is not None:
            if konkorde_val > 0:
                entry_support.append("konkorde_buy")
            elif konkorde_val < 0:
                exit_support.append("konkorde_sell")

        ao = indicators.get("ao")
        if ao is not None:
            if ao > 0:
                entry_support.append("ao_positive")
            elif ao < 0:
                exit_support.append("ao_negative")

        sma50 = indicators.get("sma50")
        ema50 = indicators.get("ema50")
        if sma50 is not None and ema50 is not None:
            if ema50 > sma50:
                entry_support.append("ema50_gt_sma50")
            elif ema50 < sma50:
                exit_support.append("ema50_lt_sma50")

        macd = indicators.get("macd")
        macd_signal = indicators.get("macd_signal")
        if macd is not None and macd_signal is not None:
            if macd > macd_signal and macd > 0:
                entry_support.append("macd_bullish")
            elif macd < macd_signal and macd < 0:
                exit_support.append("macd_bearish")

        stoch_k = indicators.get("stoch_rsi_k")
        stoch_d = indicators.get("stoch_rsi_d")
        if stoch_k is not None and stoch_d is not None:
            if stoch_k < 20 and stoch_k > stoch_d:
                entry_support.append("stoch_rsi_oversold")
            elif stoch_k > 80 and stoch_k < stoch_d:
                exit_support.append("stoch_rsi_overbought")

        # `low_volatility` reads realised volatility (20-bar stdev of returns)
        # while `vol_high` reads BBWP — two different metrics that can and do
        # disagree (live bug 2026-07-06: long side said "Baja volatilidad"
        # via volatility_20 while the short side said "Alta volatilidad" via
        # BBWP 82). When BBWP already flags exhaustion-level volatility the
        # breakout-anticipation vote is contradictory, so it is suppressed.
        volatility = indicators.get("volatility_20")
        if (
            volatility is not None
            and volatility < 1.5
            and (bbwp is None or bbwp <= th["bbwp_high"])
        ):
            entry_support.append("low_volatility")

        # ----------------------------------------------------------
        # Weighted scoring + regime adjustments
        # ----------------------------------------------------------
        regime = self._detect_regime(indicators)
        weights, regime_adjustments = self._weights_for_regime(regime)

        entry_score = sum(weights.get(self._SIGNAL_FAMILY.get(s, ""), 1.0) for s in entry_support)
        exit_score = sum(weights.get(self._SIGNAL_FAMILY.get(s, ""), 1.0) for s in exit_support)

        entry_votes = len(entry_support)
        exit_votes = len(exit_support)

        signal = "neutral"
        # Compression precedes breakouts where direction is unknown — skip.
        if regime != "compression":
            min_score = max(4.0, 0.6 * (entry_score + exit_score))
            if entry_score >= min_score and entry_score > exit_score:
                signal = "entry"
            elif exit_score >= min_score and exit_score > entry_score:
                signal = "exit"
        else:
            regime_adjustments.append("compression_blocks_signal")

        explanations = self._explanations()

        def explain(codes: List[str]) -> List[str]:
            return [explanations.get(c, c) for c in codes]

        return {
            "signal": signal,
            "regime": regime,
            "regime_adjustments": regime_adjustments,
            "entry_votes": entry_votes,
            "exit_votes": exit_votes,
            "entry_score": round(entry_score, 3),
            "exit_score": round(exit_score, 3),
            "support_entry": entry_support,
            "support_exit": exit_support,
            "explain_entry": explain(entry_support),
            "explain_exit": explain(exit_support),
        }

    # ------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------
    def _weights_for_regime(self, regime: str) -> tuple[Dict[str, float], List[str]]:
        weights = dict(self.weights)
        adjustments: List[str] = []
        if regime == "trending":
            weights["adx"] = weights.get("adx", 1.0) * 1.5
            adjustments.append("trending: x1.5 ADX weight")
        elif regime == "ranging":
            weights["rsi"] = weights.get("rsi", 1.0) * 1.5
            weights["stoch_rsi"] = weights.get("stoch_rsi", 1.0) * 1.5
            adjustments.append("ranging: x1.5 RSI / Stoch RSI weights")
        elif regime == "exhaustion":
            adjustments.append("exhaustion: divergence hook reserved")
        return weights, adjustments

    @staticmethod
    def _explanations() -> Dict[str, str]:
        return {
            "rsi_oversold": "RSI por debajo del umbral de sobreventa, posible rebote alcista",
            "rsi_overbought": "RSI por encima del umbral de sobrecompra, posible corrección",
            "vol_low": "Baja volatilidad (BBWP), posible inicio de movimiento",
            "vol_high": "Alta volatilidad (BBWP), riesgo de agotamiento o toma de ganancias",
            "adx_trend": "ADX por encima del nivel de tendencia, mercado con dirección definida",
            "adx_trend_bullish": "ADX > 25 con +DI dominante: tendencia alcista confirmada",
            "adx_trend_bearish": "ADX > 25 con -DI dominante: tendencia bajista confirmada",
            "konkorde_buy": "Konkorde indica presión compradora (línea marrón positiva)",
            "konkorde_sell": "Konkorde indica presión vendedora (línea marrón negativa)",
            "ao_positive": "Awesome Oscillator positivo, impulso alcista",
            "ao_negative": "Awesome Oscillator negativo, impulso bajista",
            "ema50_gt_sma50": "EMA50 sobre SMA50, sesgo alcista de corto plazo",
            "ema50_lt_sma50": "EMA50 bajo SMA50, sesgo bajista de corto plazo",
            "macd_bullish": "MACD por encima de su señal en territorio positivo",
            "macd_bearish": "MACD por debajo de su señal en territorio negativo",
            "stoch_rsi_oversold": "Stoch RSI en sobreventa con divergencia alcista",
            "stoch_rsi_overbought": "Stoch RSI en sobrecompra con divergencia bajista",
            "low_volatility": "Baja volatilidad realizada (desv. est. 20 velas), ambiente propicio para breakouts",
        }
