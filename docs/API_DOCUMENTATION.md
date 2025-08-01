# 📊 MCP Trading Algorítmico - Documentación de API

## 📋 Índice
- [Arquitectura General](#arquitectura-general)
- [Endpoints Disponibles](#endpoints-disponibles)
- [Ejemplos de Uso](#ejemplos-de-uso)
- [Modelos de Respuesta](#modelos-de-respuesta)

## 🏗️ Arquitectura General

### Estructura del Proyecto
```
src/
├── controllers/
│   ├── metrics/
│   │   ├── market_data_service.py    # Descarga de datos OHLCV
│   │   ├── indicators_service.py     # Cálculo de indicadores técnicos
│   │   ├── rules_service.py          # Evaluación de reglas de trading
│   │   ├── averages_service.py       # Promedios y estadísticas
│   │   ├── movements_service.py      # Recomendaciones de trading
│   │   └── dominance_service.py      # Dominancia de mercado
│   └── healthy_controller.py         # Health checks
├── routes/
│   ├── v1/
│   │   ├── metrics_routing.py        # /metrics
│   │   ├── averages_routing.py       # /averages
│   │   ├── movements_routing.py      # /movements
│   │   └── dominance_routing.py      # /dominance
│   └── healthy.py                    # Health endpoints
├── main.py                           # Punto de entrada
├── web_server.py                     # Configuración FastAPI
└── mcp_server.py                     # Configuración MCP
```

### Capas de la Aplicación
1. **Routing Layer**: Manejo de requests HTTP y validación de parámetros
2. **Service Layer**: Lógica de negocio y cálculos
3. **Data Layer**: Integración con exchanges (ccxt) y APIs externas

## 🚀 Endpoints Disponibles

### 1. Health Checks
**GET** `/healthy` - Estado de salud básico
**GET** `/liveness` - Liveness probe para Kubernetes

### 2. Métricas Básicas
**GET** `/v1/metrics/get` - Indicadores técnicos completos

### 3. Promedios y Estadísticas
**GET** `/v1/averages/` - Cálculo de promedios e identificación de rebotes

### 4. Recomendaciones de Trading
**GET** `/v1/movements/` - Señales long/short con niveles de entrada y salida

### 5. Dominancia de Mercado
**GET** `/v1/dominance/` - Análisis de dominancia y métricas por moneda

### 6. Datos para Gráficos
**GET** `/v1/charts/` - Datos OHLCV optimizados para gráficos
**GET** `/v1/charts/timeframes` - Timeframes disponibles y recomendaciones

---

## 📖 Documentación Detallada por Endpoint

### 🔍 GET `/v1/metrics/get`
**Propósito**: Obtiene indicadores técnicos completos para un símbolo específico.

**Parámetros**:
- `symbol` (string, requerido): Par de trading (ej: "BTC/USDT")
- `exchange` (string, opcional): Exchange a usar (default: "binance")
- `timeframe` (string, opcional): Marco temporal (default: "1h")
- `limit` (int, opcional): Número de velas (default: 500)

**Ejemplo de Request**:
```bash
curl -X GET \
"http://localhost:9000/v1/metrics/get?symbol=BTC/USDT&timeframe=1h&exchange=binance&limit=100"
```

**Ejemplo de Response**:
```json
{
  "exchange": "binance",
  "symbol": "BTC/USDT",
  "timeframe": "1h",
  "timestamp": "2025-07-31T16:30:00Z",
  "indicators": {
    "rsi14": 54.32,
    "adx14": 17.85,
    "bbwp": 2.45,
    "bbwp_ma4": 2.38,
    "ao": 125.67,
    "sma50": 27650.45,
    "ema50": 27680.12,
    "sma200": 26800.22,
    "ema200": 26850.78,
    "konkorde_value": 1234567.89,
    "konkorde_signal": "bullish",
    "macd": 45.67,
    "macd_signal": 42.33,
    "macd_histogram": 3.34,
    "stoch_rsi_k": 65.4,
    "stoch_rsi_d": 62.1,
    "atr": 890.45,
    "volatility_20": 2.34
  },
  "signals": {
    "signal": "entry",
    "entry_votes": 5,
    "exit_votes": 1,
    "support_entry": ["rsi_oversold", "konkorde_buy", "macd_bullish"],
    "support_exit": [],
    "explain_entry": [
      "RSI por debajo del umbral de sobreventa, posible rebote alcista",
      "Konkorde indica presión compradora (OBV > EMA)",
      "MACD por encima de su señal en territorio positivo"
    ],
    "explain_exit": []
  }
}
```

---

### 📊 GET `/v1/averages/`
**Propósito**: Calcula promedios de indicadores y detecta el mayor rebote en un periodo.

**Parámetros**:
- `symbol` (string, requerido): Par de trading
- `timeframe` (string, opcional): Marco temporal (default: "1h")
- `exchange` (string, opcional): Exchange (default: "binance")
- `start` (datetime, opcional): Fecha inicial ISO 8601
- `end` (datetime, opcional): Fecha final ISO 8601
- `span` (string, opcional): Rango retrospectivo (default: "1d"). Ejemplos: "48h", "7d", "2w", "1m"
- `indicators` (string, opcional): Lista separada por comas de indicadores a calcular
- `top_n` (int, opcional): Número de valores extremos (default: 10, rango: 1-100)

**Indicadores Disponibles**:
- `close`: Promedio de precios de cierre
- `volume`: Promedio de volumen
- `rsi`: Promedio de RSI
- `adx`: Promedio de ADX
- `highest_price`: Precio máximo del periodo
- `lowest_price`: Precio mínimo del periodo
- `highest_prices`: Lista de los N precios más altos
- `lowest_prices`: Lista de los N precios más bajos
- `avg_price`: Promedio de (high + low) / 2
- `avg_high`: Promedio de los N highs más altos
- `avg_low`: Promedio de los N lows más bajos

**Ejemplo de Request** (usando span):
```bash
curl -X GET \
"http://localhost:9000/v1/averages/?symbol=BTC/USDT&timeframe=15m&span=14d&indicators=highest_prices,lowest_prices,avg_high,avg_low&top_n=7"
```

**Ejemplo de Request** (usando fechas específicas):
```bash
curl -X GET \
"http://localhost:9000/v1/averages/?symbol=BTC/USDT&timeframe=15m&start=2025-07-25T00:00:00Z&end=2025-07-31T23:59:59Z&indicators=avg_price,highest_price,lowest_price"
```

**Ejemplo de Response**:
```json
{
  "symbol": "BTC/USDT",
  "timeframe": "15m",
  "averages": {
    "highest_prices": [121350.0, 121000.0, 120980.0, 120500.0, 120120.0, 119960.0, 119860.0],
    "avg_high": 120681.4,
    "lowest_prices": [112420.5, 112800.0, 113050.0, 113400.0, 113500.0, 113650.0, 113900.0],
    "avg_low": 113531.0
  },
  "major_rebound": {
    "date": "2025-07-27T15:00:00Z",
    "type": "bullish",
    "move_pct": 7.23
  }
}
```

---

### 🎯 GET `/v1/movements/`
**Propósito**: Genera recomendaciones de trading long/short con niveles específicos.

**Parámetros**:
- `symbol` (string, requerido): Par de trading
- `timeframe` (string, opcional): Marco temporal (default: "1h")
- `exchange` (string, opcional): Exchange (default: "binance")
- `capital` (float, opcional): Capital disponible (default: 1000.0)
- `risk_profile` (string, opcional): Perfil de riesgo: "low", "medium", "high" (default: "medium")
- `side` (string, opcional): Tipo de posición: "long", "short", "both" (default: "both")

**Perfiles de Riesgo**:
- `low`: Target 2.5%, Stop 1.5% (R:R = 1.67)
- `medium`: Target 5.0%, Stop 3.0% (R:R = 1.67)
- `high`: Target 10.0%, Stop 5.0% (R:R = 2.0)

**Ejemplo de Request**:
```bash
curl -X GET \
"http://localhost:9000/v1/movements/?symbol=BTC/USDT&timeframe=1h&risk_profile=medium&side=both&capital=5000"
```

**Ejemplo de Response**:
```json
{
  "symbol": "BTC/USDT",
  "timeframe": "1h",
  "long": {
    "entry": 27710.00,
    "target_price": 29095.50,
    "target_pct": 5.0,
    "stop_loss": 26879.70,
    "confidence": 0.78,
    "risk_reward_ratio": 1.67,
    "reasons": [
      "RSI por debajo del umbral de sobreventa, posible rebote alcista",
      "MACD por encima de su señal en territorio positivo",
      "Stoch RSI en sobreventa con divergencia alcista",
      "Baja volatilidad, ambiente propicio para breakouts"
    ]
  },
  "short": {
    "entry": 27650.00,
    "target_price": 26267.50,
    "target_pct": 5.0,
    "stop_loss": 28479.50,
    "confidence": 0.22,
    "risk_reward_ratio": 1.67,
    "reasons": [
      "RSI por encima del umbral de sobrecompra, posible corrección"
    ]
  }
}
```

---

### 🌐 GET `/v1/dominance/`
**Propósito**: Análisis de dominancia de mercado con métricas adicionales por moneda.

**Parámetros**:
- `coins` (string, opcional): Lista de monedas separadas por coma (default: "btc,eth")
- `exchange` (string, opcional): Exchange para análisis técnico (default: "binance")
- `timeframe` (string, opcional): Marco temporal para indicadores (default: "daily")
- `limit` (int, opcional): Número de velas para indicadores (default: 500)

**Ejemplo de Request**:
```bash
curl -X GET \
"http://localhost:9000/v1/dominance/?coins=btc,eth,usdt,bnb&exchange=binance&timeframe=daily&limit=100"
```

**Ejemplo de Response**:
```json
{
  "dominance": {
    "btc": 45.67,
    "eth": 18.23,
    "usdt": 5.45,
    "bnb": 3.21
  },
  "analysis": {
    "btc": {
      "exchange": "binance",
      "symbol": "BTC/USDT",
      "timeframe": "daily",
      "timestamp": "2025-07-31T16:30:00Z",
      "indicators": {
        "rsi14": 52.1,
        "adx14": 23.4,
        "macd": 234.5
      },
      "signals": {
        "signal": "entry",
        "entry_votes": 4,
        "exit_votes": 1
      }
    },
    "eth": {
      "exchange": "binance",
      "symbol": "ETH/USDT",
      "timeframe": "daily",
      "indicators": {
        "rsi14": 48.7,
        "adx14": 19.8
      },
      "signals": {
        "signal": "neutral",
        "entry_votes": 2,
        "exit_votes": 2
      }
    }
  }
}
```

---

## 🔧 Configuración y Variables de Entorno

### Variables Principales
```bash
# Servidor
PORT=9000
HOST=0.0.0.0
PREFIX_PATH=/v1

# Logging
LOG_CONFIG_PATH=src/log_conf.yaml

# Health Checks
HEALTHY_PATH=/healthy
LIVENESS_PATH=/liveness

# Trading Rules (Opcional - sobreescribe defaults)
RSI_OVERBOUGHT=70.0
RSI_OVERSOLD=30.0
ADX_TREND=25.0
BBWP_HIGH=4.0
BBWP_LOW=1.5

# Reglas por símbolo (Ejemplo)
BTC_USDT_RSI_OVERBOUGHT=75.0
ETH_USDT_RSI_OVERSOLD=25.0
```

## 🚨 Códigos de Error Comunes

### 400 Bad Request
- Parámetros inválidos o faltantes
- Formato de fecha incorrecto
- Símbolos no soportados

### 500 Internal Server Error
- Error de conexión con exchange
- Datos insuficientes para cálculos
- Problemas con APIs externas

### Ejemplo de Error:
```json
{
  "detail": "No hay suficientes velas en el rango para calcular promedios y rebotes"
}
```

## 🔄 Estrategia de Trading Implementada

### Indicadores Utilizados
1. **Momentum**: RSI, MACD, Stochastic RSI, Awesome Oscillator
2. **Tendencia**: ADX, EMAs, SMAs
3. **Volatilidad**: BBWP, ATR, Volatilidad Realizada
4. **Volumen**: OBV, Konkorde

### Sistema de Votación
- Cada indicador "vota" por entrada, salida o neutral
- Umbral dinámico: mínimo 3 votos o 60% de consenso
- Confianza basada en proporción de votos favorables

### Gestión de Riesgo
- Ratios riesgo-beneficio definidos por perfil
- Stop-loss y targets calculados automáticamente
- Consideración de volatilidad del activo

---

### 📊 GET `/v1/charts/`
**Propósito**: Obtiene datos OHLCV optimizados para gráficos con selección automática del mejor timeframe.

**Características Principales**:
- **Selección Automática**: Determina el timeframe óptimo según el rango temporal
- **Fallback Inteligente**: Si un timeframe no está disponible, prueba alternativas
- **Optimización de Puntos**: Limita los datos al número máximo especificado
- **Múltiples Exchanges**: Soporte para Binance y Bitget

**Parámetros**:
- `symbol` (string, requerido): Par de trading
- `exchange` (string, opcional): Exchange ("binance", "bitget") - default: "binance"
- `start` (datetime, opcional): Fecha inicial ISO 8601
- `end` (datetime, opcional): Fecha final ISO 8601
- `span` (string, opcional): Rango retrospectivo (default: "24h")
- `max_points` (int, opcional): Máximo puntos (50-5000) - default: 1000
- `timeframe` (string, opcional): Forzar timeframe específico

**Rangos de Span Soportados**:
- **Horas**: `1h`, `6h`, `12h`, `24h`
- **Días**: `2d`, `7d`, `14d`, `30d`
- **Semanas**: `1w`, `2w`, `4w`
- **Meses**: `1M`, `3M`, `6M`, `1y`

**Timeframes Disponibles**:
`1m`, `3m`, `5m`, `15m`, `30m`, `1h`, `2h`, `4h`, `6h`, `8h`, `12h`, `1d`, `3d`, `1w`, `1M`

**Ejemplo de Request** (automático):
```bash
curl -X GET \
"http://localhost:9000/v1/charts/?symbol=BTC/USDT&span=7d&max_points=500&exchange=binance"
```

**Ejemplo de Request** (timeframe específico):
```bash
curl -X GET \
"http://localhost:9000/v1/charts/?symbol=ETH/USDT&start=2025-07-25T00:00:00Z&end=2025-07-31T23:59:59Z&timeframe=1h"
```

**Ejemplo de Response**:
```json
{
  "symbol": "BTC/USDT",
  "exchange": "binance",
  "timeframe": "4h",
  "start": "2025-07-24T16:30:00Z",
  "end": "2025-07-31T16:30:00Z",
  "duration_hours": 168.0,
  "total_candles": 42,
  "chart_data": [
    {
      "timestamp": 1721836800000,
      "datetime": "2025-07-24T16:00:00Z",
      "open": 27680.50,
      "high": 27850.25,
      "low": 27620.10,
      "close": 27720.75,
      "volume": 1234567.89
    },
    {
      "timestamp": 1721851200000,
      "datetime": "2025-07-24T20:00:00Z",
      "open": 27720.75,
      "high": 27890.00,
      "low": 27680.30,
      "close": 27845.20,
      "volume": 987654.32
    }
  ],
  "metrics": {
    "price_range": {
      "highest": 28950.75,
      "lowest": 26850.25,
      "range_pct": 7.82
    },
    "volume": {
      "total": 50567890.12,
      "average": 1203521.67,
      "max": 3456789.01
    },
    "price_change": {
      "start_price": 27680.50,
      "end_price": 28234.80,
      "change_pct": 2.00
    },
    "volatility": {
      "daily_returns_std": 2.145,
      "price_volatility": 1.89
    }
  },
  "optimization": {
    "optimal_timeframe": "4h",
    "reason": "Timeframe óptimo 4h seleccionado automáticamente",
    "data_density": "óptima"
  }
}
```

### 🔍 GET `/v1/charts/timeframes`
**Propósito**: Lista timeframes disponibles con estimaciones para un símbolo y rango específico.

**Parámetros**:
- `symbol` (string, requerido): Par de trading
- `exchange` (string, opcional): Exchange - default: "binance"
- `span` (string, opcional): Rango temporal - default: "24h"
- `max_points` (int, opcional): Máximo puntos deseados - default: 1000

**Ejemplo de Request**:
```bash
curl -X GET \
"http://localhost:9000/v1/charts/timeframes?symbol=BTC/USDT&span=30d&max_points=200"
```

**Ejemplo de Response**:
```json
{
  "symbol": "BTC/USDT",
  "exchange": "binance",
  "span": "30d",
  "max_points": 200,
  "recommended_timeframe": "6h",
  "available_timeframes": [
    {
      "timeframe": "1m",
      "candle_duration": "1m",
      "estimated_candles": 1000,
      "density": "subóptima",
      "recommended": false
    },
    {
      "timeframe": "1h",
      "candle_duration": "1h",
      "estimated_candles": 720,
      "density": "subóptima",
      "recommended": false
    },
    {
      "timeframe": "6h",
      "candle_duration": "6h",
      "estimated_candles": 120,
      "density": "óptima",
      "recommended": true
    },
    {
      "timeframe": "1d",
      "candle_duration": "24h",
      "estimated_candles": 30,
      "density": "subóptima",
      "recommended": false
    }
  ]
}
```

### 🎯 Casos de Uso del Endpoint Charts

**1. Gráfico Intraday (Trading Activo)**
```bash
# Últimas 4 horas con máxima resolución
GET /v1/charts/?symbol=BTC/USDT&span=4h&max_points=240
# → Selecciona automáticamente 1m o 5m
```

**2. Análisis de Swing Trading**
```bash
# Últimas 2 semanas, 500 puntos máximo
GET /v1/charts/?symbol=ETH/USDT&span=14d&max_points=500
# → Selecciona automáticamente 1h o 4h
```

**3. Análisis de Tendencia a Largo Plazo**
```bash
# Últimos 6 meses, vista general
GET /v1/charts/?symbol=BTC/USDT&span=6M&max_points=180
# → Selecciona automáticamente 1d o 3d
```

**4. Rango Específico con Timeframe Forzado**
```bash
# Período exacto con timeframe específico
GET /v1/charts/?symbol=BTC/USDT&start=2025-07-01T00:00:00Z&end=2025-07-31T23:59:59Z&timeframe=4h
```

### 🔄 Lógica de Selección Automática

El algoritmo considera:

1. **Duración del Rango**: Tiempo total solicitado
2. **Densidad Óptima**: 50-1000 puntos preferiblemente
3. **Disponibilidad**: Fallback si el timeframe ideal no está disponible
4. **Prioridad**: Timeframes más granulares son preferidos cuando es posible

**Matriz de Recomendaciones**:
- **< 2 horas**: 1m o 5m
- **2-12 horas**: 15m o 30m  
- **12 horas - 3 días**: 1h
- **3-15 días**: 4h o 6h
- **15-60 días**: 1d
- **> 60 días**: 3d o 1w

---

## 📈 Próximas Mejoras

### Funcionalidades Planificadas
1. **Backtesting**: Prueba histórica de estrategias
2. **Alertas**: Notificaciones en tiempo real
3. **Portfolio**: Gestión de múltiples posiciones
4. **Machine Learning**: Predicciones basadas en ML
5. **WebSockets**: Streaming de datos en tiempo real

### Optimizaciones Técnicas
1. **Caching**: Redis para datos frecuentes
2. **Database**: Almacenamiento de históricos
3. **Monitoring**: Métricas de performance
4. **Testing**: Suite completa de tests