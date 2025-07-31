from typing import Dict
from os import getenv


class RulesService:
    """Evalúa reglas de trading (entrada, salida, neutral) con umbrales configurables.

    Los umbrales pueden definirse de tres maneras:
    1. Valores por defecto (DEFAULT_THRESHOLDS).
    2. Variables de entorno globales, p.e. RSI_OVERBOUGHT.
    3. Variables de entorno por símbolo, p.e. BTC_USDT_RSI_OVERSOLD.
    4. Parámetro `thresholds` pasado al constructor, que tiene máxima prioridad.
    """

    DEFAULT_THRESHOLDS: Dict[str, float] = {
        "rsi_overbought": 70.0,
        "rsi_oversold": 30.0,
        "adx_trend": 25.0,
        "bbwp_high": 4.0,   # volatilidad alta
        "bbwp_low": 1.5,    # volatilidad baja
    }

    def __init__(self, *, symbol: str, thresholds: Dict[str, float] | None = None):
        """symbol debe ser formato "BTC/USDT" para detectar overrides por activo."""
        self.symbol = symbol.upper().replace("/", "_")

        # 1. Partimos de los defaults
        th = self.DEFAULT_THRESHOLDS.copy()

        # 2. Overrides globales (sin símbolo)
        for key in th.keys():
            env_val = getenv(key.upper())
            if env_val is not None:
                th[key] = float(env_val)

        # 3. Overrides por símbolo
        for key in th.keys():
            env_key = f"{self.symbol}_{key.upper()}"
            env_val = getenv(env_key)
            if env_val is not None:
                th[key] = float(env_val)

        # 4. Overrides explícitos del caller
        if thresholds:
            th.update(thresholds)

        self.thresholds = th

    # ------------------------------------------------------------
    # Evaluación de señales
    # ------------------------------------------------------------
    def evaluate(self, indicators: Dict[str, float]) -> Dict[str, str]:
        """Evalúa múltiples indicadores.

        Devuelve:
        {
            signal: entry | exit | neutral,
            entry_votes: 5,
            exit_votes: 1,
            support_entry: ["rsi", "konkorde", ...],
            support_exit: []
        }
        """
        th = self.thresholds
        entry_support: list[str] = []
        exit_support: list[str] = []

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
        if adx is not None and adx > th["adx_trend"]:
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

        # EMA vs SMA 50 tendencia sencilla
        sma50 = indicators.get("sma50")
        ema50 = indicators.get("ema50")
        if sma50 is not None and ema50 is not None:
            if ema50 > sma50:
                entry_support.append("ema50_gt_sma50")
            elif ema50 < sma50:
                exit_support.append("ema50_lt_sma50")

        # Decisión final basada en mayoría (>=4 votos) y diferencia significativa
        entry_votes = len(entry_support)
        exit_votes = len(exit_support)
        signal = "neutral"
        if entry_votes >= 4 and entry_votes > exit_votes:
            signal = "entry"
        elif exit_votes >= 4 and exit_votes > entry_votes:
            signal = "exit"

        explanations = {
            "rsi_oversold": "RSI por debajo del umbral de sobreventa, posible rebote alcista",
            "rsi_overbought": "RSI por encima del umbral de sobrecompra, posible corrección",
            "vol_low": "Baja volatilidad (BBWP), posible inicio de movimiento",
            "vol_high": "Alta volatilidad (BBWP), riesgo de agotamiento o toma de ganancias",
            "adx_trend": "ADX por encima del nivel de tendencia, mercado con dirección definida",
            "konkorde_buy": "Konkorde indica presión compradora (OBV > EMA)",
            "konkorde_sell": "Konkorde indica presión vendedora (OBV < EMA)",
            "ao_positive": "Awesome Oscillator positivo, impulso alcista",
            "ao_negative": "Awesome Oscillator negativo, impulso bajista",
            "ema50_gt_sma50": "EMA50 sobre SMA50, sesgo alcista de corto plazo",
            "ema50_lt_sma50": "EMA50 bajo SMA50, sesgo bajista de corto plazo",
        }

        def explain(codes: list[str]):
            return [explanations.get(c, c) for c in codes]

        return {
            "signal": signal,
            "entry_votes": entry_votes,
            "exit_votes": exit_votes,
            "support_entry": entry_support,
            "support_exit": exit_support,
            "explain_entry": explain(entry_support),
            "explain_exit": explain(exit_support),
        }
