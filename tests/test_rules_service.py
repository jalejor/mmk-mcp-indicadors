from controllers.metrics.rules_service import RulesService


def test_rules_entry_signal():
    # Indicadores simulados para generar señal de entrada
    indicators = {
        "rsi14": 25.0,  # sobrevendido
        "adx14": 30.0,  # tendencia fuerte
        "bbwp": 2.0,
        "konkorde_value": 1000.0,  # presión compradora
    }
    rules = RulesService(symbol="BTC/USDT").evaluate(indicators)
    assert rules["signal"] == "entry"


def test_rules_exit_signal_by_rsi():
    indicators = {
        "rsi14": 75.0,  # sobrecomprado
        "adx14": 20.0,
        "bbwp": 2.0,
        "konkorde_value": -100.0,
    }
    rules = RulesService(symbol="BTC/USDT").evaluate(indicators)
    assert rules["signal"] == "exit"


def test_rules_neutral():
    indicators = {
        "rsi14": 50.0,
        "adx14": 10.0,
        "bbwp": 1.0,
        "konkorde_value": 0.0,
    }
    rules = RulesService(symbol="BTC/USDT").evaluate(indicators)
    assert rules["signal"] == "neutral"
