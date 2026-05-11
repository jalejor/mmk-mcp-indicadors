from controllers.metrics.rules_service import RulesService


def test_rules_entry_signal():
    # Indicators chosen to generate an entry signal in a trending regime.
    indicators = {
        "rsi14": 25.0,            # oversold
        "adx14": 30.0,            # trending market
        "plus_di": 28.0,          # bullish dominance
        "minus_di": 12.0,
        "bbwp": 50.0,             # transitional volatility (avoid compression block)
        "konkorde_value": 1000.0,  # buying pressure
    }
    rules = RulesService(symbol="BTC/USDT").evaluate(indicators)
    assert rules["signal"] == "entry"


def test_rules_exit_signal_by_rsi():
    indicators = {
        "rsi14": 75.0,           # overbought
        "adx14": 30.0,           # trending bearish
        "plus_di": 8.0,
        "minus_di": 28.0,
        "bbwp": 70.0,            # transitional, not exhaustion threshold
        "konkorde_value": -100.0,
    }
    rules = RulesService(symbol="BTC/USDT").evaluate(indicators)
    assert rules["signal"] == "exit"


def test_rules_neutral():
    indicators = {
        "rsi14": 50.0,
        "adx14": 22.0,
        "plus_di": 9.0,
        "minus_di": 9.0,
        "bbwp": 50.0,
        "konkorde_value": 0.0,
    }
    rules = RulesService(symbol="BTC/USDT").evaluate(indicators)
    assert rules["signal"] == "neutral"


def test_rules_adx_bullish_only_when_plus_di_dominant():
    """ADX > 25 with -DI dominant should NOT add an entry vote."""
    indicators = {
        "rsi14": 50.0,
        "adx14": 30.0,
        "plus_di": 10.0,
        "minus_di": 28.0,
        "bbwp": 50.0,
        "konkorde_value": 0.0,
    }
    rules = RulesService(symbol="BTC/USDT").evaluate(indicators)
    assert "adx_trend_bearish" in rules["support_exit"]
    assert "adx_trend_bullish" not in rules["support_entry"]


# ----------------------------------------------------------------------
# FASE 4 — weighted voting + regime filters
# ----------------------------------------------------------------------


def test_weighted_voting_konkorde_dominates():
    """Konkorde + RSI alone should reach the min_score thanks to konkorde's
    weight of 3.0 (3 + 1 = 4 >= 4)."""
    indicators = {
        "rsi14": 25.0,            # rsi_oversold
        "konkorde_value": 500.0,  # konkorde_buy
        "bbwp": 50.0,
        "adx14": 22.0,
        "plus_di": 10.0,
        "minus_di": 10.0,
    }
    rules = RulesService(symbol="BTC/USDT").evaluate(indicators)
    assert rules["entry_score"] >= 4.0
    assert rules["signal"] == "entry"


def test_compression_blocks_signal():
    """Compression regime (bbwp < 20) must override every entry vote."""
    indicators = {
        "rsi14": 25.0,
        "adx14": 30.0,
        "plus_di": 30.0,
        "minus_di": 5.0,
        "bbwp": 10.0,
        "konkorde_value": 1000.0,
        "ao": 5.0,
        "macd": 1.5,
        "macd_signal": 0.5,
    }
    rules = RulesService(symbol="BTC/USDT").evaluate(indicators)
    assert rules["regime"] == "compression"
    assert rules["signal"] == "neutral"
    assert "compression_blocks_signal" in rules["regime_adjustments"]


def test_regime_detection():
    base = {
        "rsi14": 50.0,
        "plus_di": 10.0,
        "minus_di": 10.0,
        "konkorde_value": 0.0,
    }
    svc = RulesService(symbol="BTC/USDT")
    assert svc._detect_regime({**base, "adx14": 30.0, "bbwp": 50.0}) == "trending"
    assert svc._detect_regime({**base, "adx14": 22.0, "bbwp": 10.0}) == "compression"
    assert svc._detect_regime({**base, "adx14": 10.0, "bbwp": 50.0}) == "ranging"
    assert svc._detect_regime({**base, "adx14": 22.0, "bbwp": 90.0}) == "exhaustion"


def test_backward_compat_weights_default():
    """Default weights leave the integer vote counts intact."""
    indicators = {
        "rsi14": 25.0,
        "konkorde_value": 100.0,
        "bbwp": 50.0,
        "adx14": 22.0,
        "plus_di": 10.0,
        "minus_di": 10.0,
    }
    rules = RulesService(symbol="BTC/USDT").evaluate(indicators)
    assert rules["entry_votes"] == len(rules["support_entry"])
    assert rules["exit_votes"] == len(rules["support_exit"])
