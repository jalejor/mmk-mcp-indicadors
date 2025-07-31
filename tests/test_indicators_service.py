import pandas as pd

from controllers.metrics.indicators_service import IndicatorsService


def _dummy_df():
    # 30 velas de datos ficticios
    data = {
        "timestamp": pd.date_range("2025-01-01", periods=30, freq="H"),
        "open": [100 + i for i in range(30)],
        "high": [101 + i for i in range(30)],
        "low": [99 + i for i in range(30)],
        "close": [100 + i for i in range(30)],
        "volume": [1000 + 10 * i for i in range(30)],
    }
    df = pd.DataFrame(data)
    df.set_index("timestamp", inplace=True)
    return df


def test_indicators_calculation_not_empty():
    df = _dummy_df()
    service = IndicatorsService(df)
    indicators = service.calculate_all()

    # Verificamos que todas las claves existan y no sean NaN
    expected_keys = [
        "rsi14",
        "adx14",
        "bbwp",
        "bbwp_ma4",
        "ao",
        "sma50",
        "ema50",
        "sma200",
        "ema200",
        "konkorde_value",
        "konkorde_signal",
    ]

    for key in expected_keys:
        assert key in indicators, f"Falta indicador {key}"
        assert indicators[key] is not None, f"Indicador {key} es None"
