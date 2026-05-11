from controllers.metrics.rules_service import RulesService


def test_rules_entry_signal():
    # Indicators chosen to generate an entry signal.
    indicators = {
        "rsi14": 25.0,            # oversold
        "adx14": 30.0,            # trending market
        "plus_di": 28.0,          # bullish dominance
        "minus_di": 12.0,
        "bbwp": 10.0,             # compression (percentile)
        "konkorde_value": 1000.0,  # buying pressure
    }
    rules = RulesService(symbol="BTC/USDT").evaluate(indicators)
    assert rules["signal"] == "entry"


def test_rules_exit_signal_by_rsi():
    indicators = {
        "rsi14": 75.0,           # overbought
        "adx14": 20.0,
        "plus_di": 10.0,
        "minus_di": 18.0,
        "bbwp": 90.0,            # exhaustion (percentile)
        "konkorde_value": -100.0,
    }
    rules = RulesService(symbol="BTC/USDT").evaluate(indicators)
    assert rules["signal"] == "exit"


def test_rules_neutral():
    indicators = {
        "rsi14": 50.0,
        "adx14": 10.0,
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
